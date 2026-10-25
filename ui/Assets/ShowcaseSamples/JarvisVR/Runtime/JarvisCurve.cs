using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace JarvisVR
{
  public sealed class JarvisCurve : BaseMeshEffect
  {
    public static float RadiusPixels = 1846f; // 2.4 m / 0.0013 m per px. 0 = flat.
    private const float MaxEdge = 40f;

    public static float Sag(float x)
    {
      return RadiusPixels <= 0f ? 0f : (x * x) / (2f * RadiusPixels);
    }

    /// <summary>Intersect a ray with the curved surface and return the matching point on the flat canvas plane.</summary>
    public static bool TryRayToFlat(Ray ray, Transform canvas, out Vector3 flatWorld)
    {
      flatWorld = default(Vector3);
      Vector3 o = canvas.InverseTransformPoint(ray.origin);
      Vector3 d = canvas.InverseTransformVector(ray.direction);
      float k = RadiusPixels > 0f ? 1f / (2f * RadiusPixels) : 0f;
      float a = k * d.x * d.x;
      float b = 2f * k * o.x * d.x + d.z;
      float c = k * o.x * o.x + o.z;
      float t;
      if (Mathf.Abs(a) < 1e-9f)
      {
        if (Mathf.Abs(b) < 1e-9f) return false;
        t = -c / b;
      }
      else
      {
        float disc = b * b - 4f * a * c;
        if (disc < 0f) return false;
        float s = Mathf.Sqrt(disc);
        float t1 = (-b - s) / (2f * a), t2 = (-b + s) / (2f * a);
        float lo = Mathf.Min(t1, t2), hi = Mathf.Max(t1, t2);
        t = lo > 0f ? lo : hi;
      }
      if (t < 0f) return false;
      Vector3 hit = o + d * t;
      flatWorld = canvas.TransformPoint(new Vector3(hit.x, hit.y, 0f));
      return true;
    }

    private readonly List<UIVertex> _tris = new List<UIVertex>();
    private readonly List<UIVertex> _next = new List<UIVertex>();
    private Matrix4x4 _last;

    // Moving, zooming or pulling a panel changes canvas-space x, so the bend must be rebuilt.
    private void LateUpdate()
    {
      if (RadiusPixels <= 0f || graphic == null || graphic.canvas == null) return;
      Matrix4x4 m = graphic.canvas.rootCanvas.transform.worldToLocalMatrix * transform.localToWorldMatrix;
      for (int i = 0; i < 16; i++)
      {
        if (Mathf.Abs(m[i] - _last[i]) > 0.01f)
        {
          _last = m;
          graphic.SetVerticesDirty();
          return;
        }
      }
    }

    public override void ModifyMesh(VertexHelper vh)
    {
      if (!IsActive() || RadiusPixels <= 0f || graphic.canvas == null || vh.currentVertCount == 0) return;
      Transform canvasT = graphic.canvas.rootCanvas.transform;
      Matrix4x4 toCanvas = canvasT.worldToLocalMatrix * transform.localToWorldMatrix;
      Matrix4x4 fromCanvas = toCanvas.inverse;

      _tris.Clear();
      vh.GetUIVertexStream(_tris);
      Subdivide(toCanvas);

      for (int i = 0; i < _tris.Count; i++)
      {
        UIVertex v = _tris[i];
        Vector3 p = toCanvas.MultiplyPoint3x4(v.position);
        p.z -= Sag(p.x);
        v.position = fromCanvas.MultiplyPoint3x4(p);
        _tris[i] = v;
      }

      vh.Clear();
      vh.AddUIVertexTriangleStream(_tris);
    }

    private void Subdivide(Matrix4x4 m)
    {
      for (int pass = 0; pass < 6; pass++)
      {
        bool split = false;
        _next.Clear();
        for (int i = 0; i + 2 < _tris.Count; i += 3)
        {
          UIVertex a = _tris[i], b = _tris[i + 1], c = _tris[i + 2];
          float xa = m.MultiplyPoint3x4(a.position).x;
          float xb = m.MultiplyPoint3x4(b.position).x;
          float xc = m.MultiplyPoint3x4(c.position).x;
          float ab = Mathf.Abs(xa - xb), bc = Mathf.Abs(xb - xc), ca = Mathf.Abs(xc - xa);
          float max = Mathf.Max(ab, Mathf.Max(bc, ca));
          if (max <= MaxEdge) { _next.Add(a); _next.Add(b); _next.Add(c); continue; }
          split = true;
          if (max == ab) { UIVertex mid = Mid(a, b); Tri(a, mid, c); Tri(mid, b, c); }
          else if (max == bc) { UIVertex mid = Mid(b, c); Tri(b, mid, a); Tri(mid, c, a); }
          else { UIVertex mid = Mid(c, a); Tri(c, mid, b); Tri(mid, a, b); }
        }
        _tris.Clear();
        _tris.AddRange(_next);
        if (!split) break;
      }
    }

    private void Tri(UIVertex a, UIVertex b, UIVertex c) { _next.Add(a); _next.Add(b); _next.Add(c); }

    private static UIVertex Mid(UIVertex a, UIVertex b)
    {
      UIVertex v = a;
      v.position = (a.position + b.position) * 0.5f;
      v.uv0 = (a.uv0 + b.uv0) * 0.5f;
      v.uv1 = (a.uv1 + b.uv1) * 0.5f;
      v.normal = (a.normal + b.normal) * 0.5f;
      v.tangent = (a.tangent + b.tangent) * 0.5f;
      v.color = Color32.Lerp(a.color, b.color, 0.5f);
      return v;
    }
  }
}
