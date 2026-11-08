using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace JarvisVR
{
  /// <summary>
  /// Tiny regex tokenizer that turns source code into Unity rich text, one string per line
  /// (VS Code "Dark+" colours). Colour tags never span lines, so line numbers can be prefixed safely.
  /// Handles TS/JS/C#/Java-style (// and /* */ comments) and Python (# comments, triple quotes).
  /// </summary>
  public static class JarvisSyntax
  {
    const string CComment = "6A9955", CString = "CE9178", CNumber = "B5CEA8", CKeyword = "569CD6",
                 CFlow = "C586C0", CFunc = "DCDCAA", CType = "4EC9B0", CIdent = "9CDCFE", CPunct = "D4D4D4";

    static readonly HashSet<string> Keywords = new HashSet<string>((
      "const let var function class interface type enum export import from as new this super extends implements " +
      "public private protected static readonly async await void null undefined true false typeof instanceof in of " +
      "def lambda None True False self is not and or string number boolean int float bool object namespace using " +
      "abstract override virtual get set").Split(' '));

    static readonly HashSet<string> Flow = new HashSet<string>((
      "if else for foreach while do switch case break continue return throw try catch finally yield with pass " +
      "raise except elif default").Split(' '));

    const string Core =
      @"|(?<s>""""""[\s\S]*?""""""|'''[\s\S]*?'''|""(?:\\.|[^""\\\n])*""|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)" +
      @"|(?<n>\b\d[\d_]*(?:\.\d+)?\b)|(?<w>[A-Za-z_$][\w$]*)|(?<p>[^\sA-Za-z0-9_$])";

    static readonly Regex CStyle = new Regex(@"(?<c>//[^\n]*|/\*[\s\S]*?\*/)" + Core, RegexOptions.Compiled);
    static readonly Regex Hash = new Regex(@"(?<c>#[^\n]*)" + Core, RegexOptions.Compiled);
    static readonly Regex RichTag = new Regex(@"<(?=/?(b|i|color|size|material|quad|a)\b)", RegexOptions.Compiled);

    public static string[] HighlightLines(string src, string file)
    {
      src = (src ?? "").Replace("\r", "").Replace("\t", "  ");
      bool py = file != null && file.EndsWith(".py", StringComparison.OrdinalIgnoreCase);
      Regex re = py ? Hash : CStyle;
      var lines = new List<StringBuilder> { new StringBuilder() };

      void Emit(string text, string color)
      {
        string[] parts = text.Split('\n');
        for (int i = 0; i < parts.Length; i++)
        {
          if (i > 0) lines.Add(new StringBuilder());
          if (parts[i].Length == 0) continue;
          // Legacy UI Text has no &lt; entity; only neutralise "<" if it would form a real rich-text tag.
          string t = RichTag.Replace(parts[i], "<\u200B");
          StringBuilder sb = lines[lines.Count - 1];
          if (color == null) sb.Append(t);
          else sb.Append("<color=#").Append(color).Append('>').Append(t).Append("</color>");
        }
      }

      int pos = 0;
      foreach (Match m in re.Matches(src))
      {
        if (m.Index > pos) Emit(src.Substring(pos, m.Index - pos), null);
        pos = m.Index + m.Length;
        string color;
        if (m.Groups["c"].Success) color = CComment;
        else if (m.Groups["s"].Success) color = CString;
        else if (m.Groups["n"].Success) color = CNumber;
        else if (m.Groups["w"].Success)
        {
          string w = m.Value;
          int j = pos; while (j < src.Length && src[j] == ' ') j++;
          if (Flow.Contains(w)) color = CFlow;
          else if (Keywords.Contains(w)) color = CKeyword;
          else if (j < src.Length && src[j] == '(') color = CFunc;
          else if (char.IsUpper(w[0])) color = CType;
          else color = CIdent;
        }
        else color = CPunct;
        Emit(m.Value, color);
      }
      if (pos < src.Length) Emit(src.Substring(pos), null);

      var result = new string[lines.Count];
      for (int i = 0; i < result.Length; i++) result[i] = lines[i].ToString();
      return result;
    }
  }
}
