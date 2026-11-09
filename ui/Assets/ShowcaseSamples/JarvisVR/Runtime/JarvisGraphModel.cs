using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace JarvisVR
{
  // DTO classes (GraphNodeDto, GraphEdgeDto, GraphDto, HealthDto) live in JarvisBridge.cs. They were duplicated here, which does not compile.

  public static class JarvisGraphModel
  {
    /// <summary>Placeholder graph shown until (or unless) the server's /graph answers.</summary>
    public static GraphDto Sample()
    {
      var g = new GraphDto();
      void N(string id, string name, string file, string cluster, string kind, string level = "function", string parent = "") =>
        g.nodes.Add(new GraphNodeDto { id = id, name = name, file = file, cluster = cluster, kind = kind, level = level, parent = parent });
      void E(string s, string d, string k, string file = "", int line = 0) => g.edges.Add(new GraphEdgeDto { src = s, dst = d, type = "calls", kind = k, file = file, line = line });
      N("route.delete", "DELETE /account/:id", "routes/account.ts", "api", "route", "route");
      N("auth.require", "requireAuth", "auth/requireAuth.ts", "auth", "function", "function");
      N("service.delete", "deleteAccount", "services/account.ts", "services", "function", "service");
      N("auth.owner", "checkOwner", "auth/owner.ts", "auth", "function", "function");
      N("db.delete", "users.repo.delete", "db/users.repo.ts", "db", "function", "repository");
      N("db.repo", "users.repo", "db/users.repo.ts", "db", "object", "repository");
      N("test.own-account", "deletes own account", "tests/account.test.ts", "tests", "test", "test");
      E("route.delete", "auth.require", "confirmed", "routes/account.ts", 15);
      E("route.delete", "service.delete", "confirmed", "routes/account.ts", 16);
      E("service.delete", "db.repo", "confirmed", "services/account.ts", 42);
      E("db.repo", "db.delete", "inferred", "db/users.repo.ts", 8);
      E("test.own-account", "route.delete", "runtime", "tests/account.test.ts", 23);
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
      // Dispatch based on graph type
      if (!string.IsNullOrEmpty(g.graph_type))
      {
        switch (g.graph_type)
        {
          case "control_flow":
            return LayoutControlFlow(g);
          case "data_flow":
            return LayoutDataFlow(g);
        }
      }

      // Default layout for call graphs
      return DefaultLayout(g);
    }

    /// <summary>Default layout for call graphs (existing implementation).*/
    private static Dictionary<string, Vector3> DefaultLayout(GraphDto g)
    {
      var result = new Dictionary<string, Vector3>();
      var byCluster = new Dictionary<string, List<GraphNodeDto>>();
      foreach (GraphNodeDto n in g.nodes)
      {
        string c = string.IsNullOrEmpty(n.cluster) ? "other" : n.cluster;
        if (!byCluster.TryGetValue(c, out List<GraphNodeDto> list)) byCluster[c] = list = new List<GraphNodeDto>();
        list.Add(n);
      }
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
      if (unknownTotal == byCluster.Count && result.Count > 0)
      {
        Vector3 sum = Vector3.zero;
        foreach (Vector3 v in result.Values) sum += v;
        Vector3 centre = sum / result.Count;
        foreach (string id in new List<string>(result.Keys)) result[id] -= centre;
      }
      return result;
    }

    /// <summary>Control-flow layout: top-to-bottom with branches separated horizontally.*/
    private static Dictionary<string, Vector3> LayoutControlFlow(GraphDto g)
    {
      var result = new Dictionary<string, Vector3>();
      var nodeMap = new Dictionary<string, GraphNodeDto>();
      foreach (var node in g.nodes) nodeMap[node.id] = node;

      // Compute depth from entry (ignoring loop-back edges)
      var depths = new Dictionary<string, int>();
      var visited = new HashSet<string>();

      var entry = g.nodes.FirstOrDefault(n => n.node_kind == "entry");
      if (entry == null) return DefaultLayout(g);

      depths[entry.id] = 0;
      visited.Add(entry.id);

      var queue = new System.Collections.Generic.Queue<string>();
      queue.Enqueue(entry.id);

      while (queue.Count > 0)
      {
        string current = queue.Dequeue();
        int currentDepth = depths[current];

        foreach (var edge in g.edges)
        {
          if (edge.src == current && edge.edge_kind != "loop_back")
          {
            if (!visited.Contains(edge.dst))
            {
              visited.Add(edge.dst);
              depths[edge.dst] = currentDepth + 1;
              queue.Enqueue(edge.dst);
            }
          }
        }
      }

      var byDepth = new Dictionary<int, List<string>>();
      int maxDepth = 0;
      foreach (var kvp in depths)
      {
        if (!byDepth.ContainsKey(kvp.Value)) byDepth[kvp.Value] = new List<string>();
        byDepth[kvp.Value].Add(kvp.Key);
        maxDepth = Mathf.Max(maxDepth, kvp.Value);
      }

      for (int depth = 0; depth <= maxDepth; depth++)
      {
        if (!byDepth.ContainsKey(depth)) continue;
        var nodesAtDepth = byDepth[depth];
        float y = 0.3f - (depth * 0.15f);

        for (int i = 0; i < nodesAtDepth.Count; i++)
        {
          string nodeId = nodesAtDepth[i];
          var node = nodeMap[nodeId];
          float x = (i - (nodesAtDepth.Count - 1) / 2f) * 0.15f;
          float z = 0f;
          if (node.node_kind == "condition") x = 0f;
          result[nodeId] = new Vector3(x, y, z);
        }
      }

      return result;
    }

    /// <summary>Data-flow layout: left-to-right data propagation.*/
    private static Dictionary<string, Vector3> LayoutDataFlow(GraphDto g)
    {
      var result = new Dictionary<string, Vector3>();
      var parameters = g.nodes.Where(n => n.node_kind == "parameter").ToList();
      var definitions = g.nodes.Where(n => n.node_kind == "definition").ToList();
      var operations = g.nodes.Where(n => n.node_kind == "operation").ToList();
      var uses = g.nodes.Where(n => n.node_kind == "use").ToList();

      for (int i = 0; i < parameters.Count; i++)
      {
        float y = (i - (parameters.Count - 1) / 2f) * 0.12f;
        result[parameters[i].id] = new Vector3(-0.4f, y, 0f);
      }

      var middleNodes = definitions.Concat(operations).ToList();
      for (int i = 0; i < middleNodes.Count; i++)
      {
        float y = (i - (middleNodes.Count - 1) / 2f) * 0.1f;
        result[middleNodes[i].id] = new Vector3(0f, y, 0f);
      }

      for (int i = 0; i < uses.Count; i++)
      {
        float y = (i - (uses.Count - 1) / 2f) * 0.12f;
        result[uses[i].id] = new Vector3(0.4f, y, 0f);
      }

      return result;
    }
  }
}
