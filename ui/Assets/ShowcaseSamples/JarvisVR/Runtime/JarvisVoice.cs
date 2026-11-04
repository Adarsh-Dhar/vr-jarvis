using System;
using UnityEngine;
#if UNITY_ANDROID && !UNITY_EDITOR
using UnityEngine.Android;
#endif
#if JARVIS_META_VOICE
using Oculus.Voice;
#endif

namespace JarvisVR
{
  public sealed class JarvisVoice : MonoBehaviour
  {
    public enum State { Idle, Listening, Speaking }

    public static JarvisVoice Instance { get; private set; }
    public State Current { get; private set; }
    public float Level { get; private set; } // 0..1
    public event Action<string> Transcript;
    public event Action<string> Notice;

    /// <summary>Set by the workspace. Sends a 16 kHz mono WAV to the server and returns the transcript, so speech to text
    /// works on a Quest build without the Meta Voice SDK.</summary>
    public Action<byte[], Action<string>, Action<string>> Transcriber;
    private bool _recording, _heardVoice;
    private int _recStart;
    private float _recStartedAt, _lastVoiceAt;
    private const int LoopSeconds = 30, MaxRecordSeconds = 12;
    private const float SilenceStopSeconds = 1.1f, NoSpeechGiveUpSeconds = 6f, VoiceLevel = 0.15f;

    private const int Rate = 16000;
    private readonly float[] _buf = new float[256];
    private AudioClip _mic;
    private float _retryAt;
    private float _speakStartedAt;
    private float _speakUntil; // editor simulation

    private void Awake() { Instance = this; }

    private void Start()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
      if (!Permission.HasUserAuthorizedPermission(Permission.Microphone))
        Permission.RequestUserPermission(Permission.Microphone);
      InitTts();
#endif
#if JARVIS_META_VOICE
      WireStt();
#endif
    }

    public void ToggleListening()
    {
      if (Current == State.Listening) StopListening(); else StartListening();
    }

    public void StartListening()
    {
      Current = State.Listening;
#if JARVIS_META_VOICE
      if (_wit != null) { _wit.Activate(); return; }
#else
      // Record the microphone; the server transcribes it. Stops by itself after a pause, or tap the orb again to send.
      if (Transcriber != null && _mic != null && Microphone.IsRecording(null))
      {
        _recStart = Microphone.GetPosition(null);
        _recStartedAt = _lastVoiceAt = Time.unscaledTime;
        _heardVoice = false;
        _recording = true;
        return;
      }
#endif
#if UNITY_EDITOR
      // Simulator fallback so the flow is testable without a microphone.
      Invoke(nameof(DemoTranscript), 1.2f);
#else
      if (Notice != null) Notice(_mic == null ? "No microphone available. Allow microphone access for this app." : "Speech-to-text needs the server: turn off mock mode, or install the Meta Voice SDK (define JARVIS_META_VOICE).");
      Current = State.Idle;
#endif
    }

    public void StopListening()
    {
      CancelInvoke(nameof(DemoTranscript));
#if !JARVIS_META_VOICE
      if (_recording) { FinishRecording(false); return; }   // tapping the orb again sends what was said so far
#endif
#if JARVIS_META_VOICE
      if (_wit != null) _wit.Deactivate();
#endif
      if (Current == State.Listening) Current = State.Idle;
    }

#if !JARVIS_META_VOICE
    private void FinishRecording(bool discard)
    {
      _recording = false;
      if (Current == State.Listening) Current = State.Idle;
      int end = Microphone.GetPosition(null);
      int total = _mic != null ? _mic.samples : 0;
      int count = end >= _recStart ? end - _recStart : total - _recStart + end;   // the microphone buffer loops
      if (_mic == null || discard || count < Rate / 4)
      {
        if (Notice != null) Notice(discard ? "I did not hear anything. Pinch the orb and try again." : "That was too short. Try again.");
        return;
      }
      var data = new float[count];
      if (end >= _recStart) _mic.GetData(data, _recStart);
      else
      {
        var head = new float[total - _recStart];
        _mic.GetData(head, _recStart);
        Array.Copy(head, 0, data, 0, head.Length);
        if (end > 0)
        {
          var tail = new float[end];
          _mic.GetData(tail, 0);
          Array.Copy(tail, 0, data, head.Length, tail.Length);
        }
      }
      if (Notice != null) Notice("Transcribing…");
      Transcriber(EncodeWav(data, Rate),
        text =>
        {
          if (string.IsNullOrWhiteSpace(text)) { if (Notice != null) Notice("I could not make out any words."); }
          else SubmitTranscript(text.Trim());
        },
        err => { if (Notice != null) Notice("Speech-to-text failed: " + err); });
    }

    /// <summary>16-bit PCM mono WAV (44-byte header).</summary>
    private static byte[] EncodeWav(float[] samples, int rate)
    {
      int n = samples.Length;
      var b = new byte[44 + n * 2];
      void Tag(int o, string s) { for (int i = 0; i < 4; i++) b[o + i] = (byte)s[i]; }
      void I32(int o, int v) { b[o] = (byte)v; b[o + 1] = (byte)(v >> 8); b[o + 2] = (byte)(v >> 16); b[o + 3] = (byte)(v >> 24); }
      void I16(int o, int v) { b[o] = (byte)v; b[o + 1] = (byte)(v >> 8); }
      Tag(0, "RIFF"); I32(4, 36 + n * 2); Tag(8, "WAVE"); Tag(12, "fmt "); I32(16, 16); I16(20, 1); I16(22, 1);
      I32(24, rate); I32(28, rate * 2); I16(32, 2); I16(34, 16); Tag(36, "data"); I32(40, n * 2);
      for (int i = 0; i < n; i++) I16(44 + i * 2, Mathf.Clamp(Mathf.RoundToInt(samples[i] * 32767f), -32768, 32767));
      return b;
    }
#endif

    private void DemoTranscript() { SubmitTranscript("What breaks if I change deleteAccount?"); }

    public void SubmitTranscript(string text)
    {
      if (Current == State.Listening) Current = State.Idle;
      if (!string.IsNullOrEmpty(text) && Transcript != null) Transcript(text);
    }

    public void Speak(string text)
    {
      if (string.IsNullOrEmpty(text)) return;
      Current = State.Speaking;
      _speakStartedAt = Time.unscaledTime;
      _speakUntil = Time.unscaledTime + Mathf.Clamp(text.Length * 0.055f, 1f, 12f);
#if UNITY_ANDROID && !UNITY_EDITOR
      SpeakNative(text);
#endif
    }

    private void Update()
    {
#if !JARVIS_META_VOICE
      if (_mic == null && Time.unscaledTime >= _retryAt)
      {
        _retryAt = Time.unscaledTime + 2f;
        if (Microphone.devices.Length > 0) _mic = Microphone.Start(null, true, LoopSeconds, Rate);
      }
      if (_mic != null)
      {
        int pos = Microphone.GetPosition(null);
        if (pos >= _buf.Length)
        {
          _mic.GetData(_buf, pos - _buf.Length);
          float sum = 0f;
          for (int i = 0; i < _buf.Length; i++) sum += _buf[i] * _buf[i];
          float rms = Mathf.Clamp01(Mathf.Sqrt(sum / _buf.Length) * 8f);
          Level = Mathf.Lerp(Level, rms, 0.5f);
        }
      }
      if (_recording)
      {
        float now = Time.unscaledTime;
        if (Level > VoiceLevel) { _lastVoiceAt = now; _heardVoice = true; }
        float t = now - _recStartedAt;
        if (_heardVoice && now - _lastVoiceAt > SilenceStopSeconds) FinishRecording(false);
        else if (t >= MaxRecordSeconds) FinishRecording(false);
        else if (!_heardVoice && t >= NoSpeechGiveUpSeconds) FinishRecording(true);
      }
#endif
      if (Current == State.Speaking)
      {
        Level = 0.25f + 0.15f * Mathf.Sin(Time.unscaledTime * 12f);
        bool done = Time.unscaledTime >= _speakUntil;
#if UNITY_ANDROID && !UNITY_EDITOR
        done = _ttsReady && Time.unscaledTime - _speakStartedAt > 0.4f && !_tts.Call<bool>("isSpeaking");
#endif
        if (done) Current = State.Idle;
      }
    }

#if UNITY_ANDROID && !UNITY_EDITOR
    // VERIFY on device: Quest must have a text-to-speech engine. If not, use the Voice SDK TTSSpeaker.
    private AndroidJavaObject _tts;
    private bool _ttsReady;

    private sealed class TtsInit : AndroidJavaProxy
    {
      private readonly Action<int> _cb;
      public TtsInit(Action<int> cb) : base("android.speech.tts.TextToSpeech$OnInitListener") { _cb = cb; }
      public void onInit(int status) { _cb(status); }
    }

    private void InitTts()
    {
      using (AndroidJavaClass player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
      {
        AndroidJavaObject activity = player.GetStatic<AndroidJavaObject>("currentActivity");
        _tts = new AndroidJavaObject("android.speech.tts.TextToSpeech", activity, new TtsInit(s => _ttsReady = s == 0));
      }
    }

    private void SpeakNative(string text)
    {
      if (!_ttsReady) return;
      _tts.Call<int>("speak", text, 0, (AndroidJavaObject)null, "jarvis"); // 0 = QUEUE_FLUSH
    }
#endif

#if JARVIS_META_VOICE
    // VERIFY these Voice SDK member names against the version you install.
    private AppVoiceExperience _wit;

    private void WireStt()
    {
      _wit = FindFirstObjectByType<AppVoiceExperience>();
      if (_wit == null) return;
      _wit.VoiceEvents.OnFullTranscription.AddListener(SubmitTranscript);
      _wit.VoiceEvents.OnMicLevelChanged.AddListener(l => Level = Mathf.Clamp01(l * 4f));
      _wit.VoiceEvents.OnStoppedListening.AddListener(() => { if (Current == State.Listening) Current = State.Idle; });
    }
#endif
  }
}
