using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR
{
  public enum FontRole { Auto, Heading, Body, Mono }

  public static class JarvisFonts
  {
    private static readonly Dictionary<string, Font> Cache = new Dictionary<string, Font>();
    private static readonly char[] CodeChars = { '/', '(', ')', '_', ':', '{', '}', ';', '=' };
    private static Font _fallback;

    private static Font Fallback()
    {
      if (_fallback == null) _fallback = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
      return _fallback;
    }

    private static Font Load(string file)
    {
      if (Cache.TryGetValue(file, out Font cached) && cached != null) return cached;
      Font f = Resources.Load<Font>("Fonts/" + file);
      if (f == null) f = Fallback();
      Cache[file] = f;
      return f;
    }

    public static Font Heading() { return Load("SpaceGrotesk-Bold"); }

    public static void Resolve(FontRole role, string text, FontStyle style, out Font font, out FontStyle outStyle)
    {
      if (role == FontRole.Auto) role = Infer(text, style);
      bool bold = (style & FontStyle.Bold) != 0;
      switch (role)
      {
        case FontRole.Heading: font = Heading(); break;
        case FontRole.Mono: font = Load(bold ? "JetBrainsMono-Bold" : "JetBrainsMono-Regular"); break;
        default: font = Load(bold ? "Inter-SemiBold" : "Inter-Regular"); break;
      }
      // Weights are separate files, so only synthesize bold if we fell back.
      outStyle = font == Fallback() ? style : FontStyle.Normal;
    }

    private static FontRole Infer(string text, FontStyle style)
    {
      if (string.IsNullOrEmpty(text)) return FontRole.Body;
      if (text.IndexOfAny(CodeChars) >= 0) return FontRole.Mono;
      bool bold = (style & FontStyle.Bold) != 0;
      if (text == "JARVIS") return FontRole.Heading;
      if (bold && text.Length > 2 && text == text.ToUpperInvariant()) return FontRole.Heading;
      return FontRole.Body;
    }
  }
}
