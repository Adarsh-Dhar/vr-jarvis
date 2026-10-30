using System;
using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR
{
  // DTO classes (GraphNodeDto, GraphEdgeDto, GraphDto, HealthDto) live in JarvisBridge.cs. They were duplicated here, which does not compile.

  public static class JarvisGraphModel
  {
    /// <summary>Shown until (or unless) the server's /graph answers. Same ids as the fixtures in JarvisWorkspaceBootstrap.</summary>
    public static GraphDto Sample()
    {
      var g = new GraphDto();
      void N(string id, string name, string file, string cluster, string kind) =>
        g.nodes.Add(new GraphNodeDto { id = id, name = name, file = file, cluster = cluster, kind = kind });
      void E(string s, string d, string k) => g.edges.Add(new GraphEdgeDto { src = s, dst = d, type = "calls", kind = k });
      N("route.delete", "DELETE /account/:id", "routes/account.ts", "api", "route");
      N("auth.require", "requireAuth", "auth/requireAuth.ts", "auth", "function");
      N("service.delete", "deleteAccount", "services/account.ts", "services", "function");
      N("auth.owner", "checkOwner", "auth/owner.ts", "auth", "function");
      N("db.delete", "users.repo.delete", "db/users.repo.ts", "db", "function");
      N("db.repo", "users.repo", "db/users.repo.ts", "db", "object");
      N("test.own-account", "deletes own account", "tests/account.test.ts", "tests", "test");
      E("route.delete", "auth.require", "confirmed");
      E("route.delete", "service.delete", "confirmed");
      E("service.delete", "db.repo", "confirmed");
      E("db.repo", "db.delete", "inferred");
      E("test.own-account", "route.delete", "runtime");
      return g;
    }

    private static readonly Dictionary<string, Vector3> Anchors = new Dictionary<string, Vector3>
    {
      { "api", new Vector3(-0.85f, 0.15f, 0f) },
      { "auth", new Vector3(-0.30f, 0.55f, -0.10f) },
      { "services", new Vector3(0.15f, 0.10f, 0.10f) },
      { "db", new Vector3(0.75f, -0.20f, 0f) },
      { "tests", new Vector3(-0.55f, -0.40f, 0.10f) },
      { "lib", new Vector3(0.65f, 0.55f, 0f) },
    };

    /// <summary>Evenly spread unit-sphere point i of n (Fibonacci sphere).</summary>
    private static Vector3 Sphere(int i, int n)
    {
      if (n <= 1) return Vector3.zero;
      float y = 1f - 2f * (i + 0.5f) / n;
      float r = Mathf.Sqrt(Mathf.Max(0f, 1f - y * y));
      float phi = i * 2.399963f;
      return new Vector3(Mathf.Cos(phi) * r, y * 0.8f, Mathf.Sin(phi) * r);
    }

    /// <summary>Deterministic 3D layout in metres, one anchor per cluster, members on a small ring or sphere.</summary>
    public static Dictionary<string, Vector3> Layout(GraphDto g)
    {
      var result = new Dictionary<string, Vector3>();
      var byCluster = new Dictionary<string, List<GraphNodeDto>>();
      foreach (GraphNodeDto n in g.nodes)
      {
        string c = string.IsNullOrEmpty(n.cluster) ? "other" : n.cluster;
        if (!byCluster.TryGetValue(c, out List<GraphNodeDto> list)) byCluster[c] = list = new List<GraphNodeDto>();
        list.Add(n);
      }
      // Known demo clusters keep their hand-placed anchors. Any other cluster (every real repository) is spread
      // in 3D: cluster centres on a sphere around the origin, members on a small sphere around their centre.
      int unknownTotal = 0;
      foreach (string key in byCluster.Keys) if (!Anchors.ContainsKey(key)) unknownTotal++;
      int unknown = 0;
      foreach (var kv in byCluster)
      {
        int count = kv.Value.Count;
        Vector3 anchor;
        if (!Anchors.TryGetValue(kv.Key, out anchor))
        {
          anchor = unknownTotal <= 1 ? Vector3.zero : Sphere(unknown, unknownTotal) * Mathf.Min(0.75f + 0.08f * unknownTotal, 1.4f);
          unknown++;
          float radius = count > 1 ? 0.12f + 0.14f * Mathf.Pow(count, 1f / 3f) : 0f;
          for (int i = 0; i < count; i++) result[kv.Value[i].id] = anchor + Sphere(i, count) * radius;
          continue;
        }
        for (int i = 0; i < count; i++)
        {
          Vector3 offset = Vector3.zero;
          if (count > 1)
          {
            float a = i * Mathf.PI * 2f / count + 0.6f;
            float r = count > 6 ? 0.17f + 0.02f * count : 0.17f;
            offset = new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r * 0.82f, 0.04f * i);
          }
          result[kv.Value[i].id] = anchor + offset;
        }
      }
      if (unknownTotal == byCluster.Count && result.Count > 0)   // real repo: keep the whole graph centred in front of the user
      {
        Vector3 sum = Vector3.zero;
        foreach (Vector3 v in result.Values) sum += v;
        Vector3 centre = sum / result.Count;
        foreach (string id in new List<string>(result.Keys)) result[id] -= centre;
      }
      return result;
    }
  }
}
