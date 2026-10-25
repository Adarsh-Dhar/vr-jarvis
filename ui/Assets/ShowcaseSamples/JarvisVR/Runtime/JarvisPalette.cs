using UnityEngine;

namespace JarvisVR
{
  [CreateAssetMenu(menuName = "JARVIS/Palette", fileName = "JarvisPalette")]
  public sealed class JarvisPalette : ScriptableObject
  {
    public Color SpaceTop = new Color32(0x05, 0x08, 0x0F, 0xFF);
    public Color SpaceBottom = new Color32(0x10, 0x21, 0x3B, 0xFF);
    public Color Glass = new Color(14f / 255f, 22f / 255f, 38f / 255f, 0.78f);
    public Color PanelRaised = new Color32(0x13, 0x23, 0x38, 0xFF);
    public Color Cyan = new Color32(0x5E, 0xE1, 0xFF, 0xFF);   // structure
    public Color Amber = new Color32(0xFF, 0xB5, 0x47, 0xFF);  // change
    public Color Red = new Color32(0xFF, 0x6B, 0x6B, 0xFF);    // risk
    public Color Green = new Color32(0x4A, 0xDE, 0x80, 0xFF);  // verified
    public Color Violet = new Color32(0xB7, 0x9C, 0xFF, 0xFF); // AI guessed
    public Color Text = new Color32(0xE6, 0xEE, 0xF8, 0xFF);
    public Color TextMuted = new Color32(0x9F, 0xB0, 0xC6, 0xFF);

    private static JarvisPalette _current;

    public static JarvisPalette Current
    {
      get
      {
        if (_current == null) _current = Resources.Load<JarvisPalette>("JarvisPalette");
        if (_current == null) _current = CreateInstance<JarvisPalette>();
        return _current;
      }
    }
  }
}
