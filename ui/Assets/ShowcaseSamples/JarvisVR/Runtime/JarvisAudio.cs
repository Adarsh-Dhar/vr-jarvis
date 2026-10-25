using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR
{
  public static class JarvisAudio
  {
    public enum Cue { SelectTick, ExpandWhoosh, PathPulse, RiskPing, TestPass, TestFail, ApproveClick }

    public static float Volume = 0.6f;
    private const int Rate = 24000;
    private static readonly Dictionary<Cue, AudioClip> Clips = new Dictionary<Cue, AudioClip>();
    private static AudioSource _oneShot;
    private static AudioSource _charge;

    private static void Ensure()
    {
      if (_oneShot != null) return;
      GameObject go = new GameObject("JARVIS Audio");
      Object.DontDestroyOnLoad(go);
      _oneShot = go.AddComponent<AudioSource>();
      _oneShot.spatialBlend = 0f;
      _charge = go.AddComponent<AudioSource>();
      _charge.spatialBlend = 0f;
      _charge.loop = true;
      _charge.clip = Tone(160f, 160f, 1f, 0.5f, false); // whole cycles, loops cleanly
    }

    public static void Play(Cue cue)
    {
      Ensure();
      AudioClip clip;
      if (!Clips.TryGetValue(cue, out clip) || clip == null) { clip = Build(cue); Clips[cue] = clip; }
      _oneShot.PlayOneShot(clip, Volume);
    }

    /// <summary>Rising hum during the 2 s approve hold. 0 stops it.</summary>
    public static void SetCharge(float p)
    {
      Ensure();
      if (p <= 0f) { if (_charge.isPlaying) _charge.Stop(); return; }
      if (!_charge.isPlaying) _charge.Play();
      _charge.volume = Volume * Mathf.Lerp(0.15f, 0.9f, p);
      _charge.pitch = Mathf.Lerp(0.8f, 1.8f, p);
    }

    private static AudioClip Build(Cue cue)
    {
      switch (cue)
      {
        case Cue.SelectTick: return Tone(1800f, 1200f, 0.05f, 0.35f, true);
        case Cue.ExpandWhoosh: return Whoosh(0.28f, 0.5f);
        case Cue.PathPulse: return Tone(180f, 360f, 0.5f, 0.35f, true);
        case Cue.RiskPing: return Tone(520f, 520f, 0.4f, 0.3f, true);
        case Cue.TestPass: return TwoNote(660f, 880f, 0.12f, 0.4f);
        case Cue.TestFail: return TwoNote(330f, 247f, 0.16f, 0.35f);
        default: return Tone(900f, 700f, 0.07f, 0.5f, true); // ApproveClick
      }
    }

    private static AudioClip Tone(float f0, float f1, float seconds, float vol, bool decay)
    {
      int n = (int)(Rate * seconds);
      float[] d = new float[n];
      float phase = 0f;
      for (int i = 0; i < n; i++)
      {
        float t = i / (float)n;
        phase += 2f * Mathf.PI * Mathf.Lerp(f0, f1, t) / Rate;
        float env = decay ? Mathf.Pow(1f - t, 2f) * Mathf.Min(1f, i / 200f) : 1f;
        d[i] = Mathf.Sin(phase) * vol * env;
      }
      return Make(d);
    }

    private static AudioClip TwoNote(float a, float b, float noteSeconds, float vol)
    {
      int n = (int)(Rate * noteSeconds);
      float[] d = new float[n * 2];
      for (int note = 0; note < 2; note++)
      {
        float f = note == 0 ? a : b;
        for (int i = 0; i < n; i++)
        {
          float t = i / (float)n;
          d[note * n + i] = Mathf.Sin(2f * Mathf.PI * f * i / Rate) * vol * Mathf.Pow(1f - t, 1.5f) * Mathf.Min(1f, i / 150f);
        }
      }
      return Make(d);
    }

    private static AudioClip Whoosh(float seconds, float vol)
    {
      int n = (int)(Rate * seconds);
      float[] d = new float[n];
      System.Random rnd = new System.Random(7);
      float lp = 0f;
      for (int i = 0; i < n; i++)
      {
        float t = i / (float)n;
        float noise = (float)(rnd.NextDouble() * 2.0 - 1.0);
        lp += Mathf.Lerp(0.02f, 0.35f, Mathf.Sin(t * Mathf.PI)) * (noise - lp);
        d[i] = Mathf.Clamp(lp * Mathf.Sin(t * Mathf.PI) * vol * 3f, -1f, 1f);
      }
      return Make(d);
    }

    private static AudioClip Make(float[] data)
    {
      AudioClip c = AudioClip.Create("jarvis_cue", data.Length, 1, Rate, false);
      c.SetData(data, 0);
      return c;
    }
  }
}
