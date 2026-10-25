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
#endif
#if UNITY_EDITOR
      // Simulator fallback so the flow is testable without a microphone.
      Invoke(nameof(DemoTranscript), 1.2f);
#else
      if (Notice != null) Notice("Speech-to-text needs the Meta Voice SDK. Define JARVIS_META_VOICE after installing it.");
      Current = State.Idle;
#endif
    }

    public void StopListening()
    {
      CancelInvoke(nameof(DemoTranscript));
#if JARVIS_META_VOICE
      if (_wit != null) _wit.Deactivate();
#endif
      if (Current == State.Listening) Current = State.Idle;
    }

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
        if (Microphone.devices.Length > 0) _mic = Microphone.Start(null, true, 1, Rate);
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
