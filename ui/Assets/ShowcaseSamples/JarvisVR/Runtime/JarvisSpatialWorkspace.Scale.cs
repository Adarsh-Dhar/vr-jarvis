using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR
{
  /// <summary>
  /// Scale support: thousands of nodes stay as data until their cluster opens.
  /// Only cluster anchors are built up front; members materialize on expand and
  /// dematerialize (back to pending data) when the node budget forces it.
  /// </summary>
  public sealed partial class JarvisSpatialWorkspace
  {
    private const int MaxVisibleNodes = 1500, MaxVisibleEdges = 3000;
    private Dictionary<string, Vector3> _layout = new Dictionary<string, Vector3>();
    private readonly Dictionary<string, GraphNodeDto> _dtoById = new Dictionary<string, GraphNodeDto>();
    private readonly Dictionary<string, List<GraphEdgeDto>> _edgesByNode = new Dictionary<string, List<GraphEdgeDto>>();
    private readonly HashSet<string> _edgeKeys = new HashSet<string>();
    private readonly LinkedList<string> _clusterLru = new LinkedList<string>();
    private readonly Dictionary<string, int> _clusterNext = new Dictionary<string, int>();
    private List<NodeView> _lodList = new List<NodeView>();
    private int _lodCursor;

    // =========================================================== graph data index

    private void IndexGraphData(GraphDto g)
    {
      if (g.nodes != null) foreach (var n in g.nodes) if (n != null) _dtoById[n.id] = n;
      if (g.edges == null) return;
      foreach (var e in g.edges) { AddEdgeIndex(e.src, e); AddEdgeIndex(e.dst, e); }
    }

    private void AddEdgeIndex(string id, GraphEdgeDto e)
    {
      if (string.IsNullOrEmpty(id)) return;
      if (!_edgesByNode.TryGetValue(id, out var l)) _edgesByNode[id] = l = new List<GraphEdgeDto>();
      l.Add(e);
    }

    /// <summary>Create EdgeViews for every indexed edge touching <paramref name="id"/>
    /// whose other end is already built. Safe to call repeatedly; _edgeKeys dedupes.</summary>
    private void TryCreateEdges(string id)
    {
      if (!_edgesByNode.TryGetValue(id, out var list)) return;
      foreach (var e in list)
      {
        if (string.IsNullOrEmpty(e.src) || string.IsNullOrEmpty(e.dst)) continue;
        if (!_nodes.TryGetValue(e.src, out var a) || !_nodes.TryGetValue(e.dst, out var b)) continue;
        if (!_edgeKeys.Add(EdgeKey(e))) continue;
        a.Out++; b.In++;
        var ev = new EdgeView { Dto = e, From = a, To = b };
        _edges.Add(ev);
        DrawEdge(ev);
      }
      _edgesDirty = true;
    }

    // =========================================================== lazy node build

    /// <summary>The visible part of a cluster: member 0 is the always-built anchor,
    /// the rest are NodeViews created on expand. Pending holds not-yet-built DTOs.</summary>
    private NodeView CreateNodeView(GraphNodeDto dto, ClusterView cv, Vector3 pos)
    {
      JarvisPalette pal = JarvisPalette.Current;
      var nv = new NodeView { Dto = dto, Cluster = cv };
      var rootGo = new GameObject("Node " + dto.id);
      rootGo.transform.SetParent(_graphRoot, false);
      rootGo.transform.localPosition = pos;
      nv.Root = rootGo.transform;

      // Choose primitive based on level (module, file, class, function, layer, external)
      PrimitiveType shape = dto.level == "module" ? PrimitiveType.Cube
        : dto.level == "file" ? PrimitiveType.Cube
        : dto.level == "class" ? PrimitiveType.Cylinder
        : dto.level == "layer" ? PrimitiveType.Capsule
        : dto.kind == "external" ? PrimitiveType.Cube
        : PrimitiveType.Sphere;

      GameObject body = GameObject.CreatePrimitive(shape);
      body.name = "Body";
      body.transform.SetParent(rootGo.transform, false);

      // Scale based on level
      float scale = dto.level == "module" ? 0.12f
        : dto.level == "file" ? 0.10f
        : dto.level == "class" ? 0.08f
        : dto.level == "layer" ? 0.14f
        : dto.kind == "external" ? 0.06f
        : 0.075f;
      body.transform.localScale = Vector3.one * scale;

      // Rotate layer nodes (ring-like)
      if (dto.level == "layer")
      {
        body.transform.localRotation = Quaternion.Euler(0f, 0f, 45f);
      }
      // Rotate external nodes (diamond-like)
      else if (dto.kind == "external")
      {
        body.transform.localRotation = Quaternion.Euler(45f, 45f, 0f);
      }

      nv.BodyT = body.transform;
      nv.Body = body.GetComponent<Renderer>();
      nv.Body.sharedMaterial = JarvisSpatialGfx.Neon(Color.white, 1.5f, true);
      JarvisSpatialGfx.Flat(nv.Body);

      // Ensure the node collider is not a trigger so it can be raycast against
      Collider nodeCollider = body.GetComponent<Collider>();
      if (nodeCollider != null) nodeCollider.isTrigger = false;

      Color baseColor = dto.level == "module" ? pal.Amber
        : dto.level == "file" ? pal.Violet
        : dto.level == "class" ? pal.Green
        : dto.level == "layer" ? pal.Red
        : dto.kind == "external" ? pal.Gray
        : dto.kind == "test" ? pal.Violet
        : pal.Cyan;

      nv.Base = baseColor;
      body.AddComponent<JarvisGraphNode>().Initialize(dto.id, Select, DragCluster, ShowNodeMenu);
      // Invisible pinch target: the rendered node is only a few centimetres wide, which is
      // hard to hit reliably at arm's length. Parent it to Body so it grows with the pop animation.
      var hitArea = new GameObject("HitArea");
      hitArea.transform.SetParent(body.transform, false);
      hitArea.transform.localScale = Vector3.one * 2.4f;
      hitArea.AddComponent<SphereCollider>();
      nv.Fx = rootGo.AddComponent<JarvisNodeFx>();
      nv.Fx.Begin(nv.BodyT, 0.06f * _nodes.Count, nv.Base);

      nv.Label = MakeLabel(rootGo.transform, dto.name, pal.Text, LabelSize, new Vector3(0f, -0.085f, 0f));
      cv.Members.Add(nv);
      _nodes[dto.id] = nv;
      return nv;
    }

    private ClusterView GetOrCreateCluster(string name)
    {
      if (_clusters.TryGetValue(name, out ClusterView cv)) return cv;
      JarvisPalette pal = JarvisPalette.Current;
      cv = new ClusterView { Name = name, Collapsed = false };
      _clusters[name] = cv;

      var shell = GameObject.CreatePrimitive(PrimitiveType.Sphere);
      shell.name = "ClusterShell " + cv.Name;
      Destroy(shell.GetComponent<Collider>());   // never blocks node pinch rays
      shell.transform.SetParent(_graphRoot, false);
      Renderer r = shell.GetComponent<Renderer>();
      Material shellMat = JarvisSpatialGfx.Shell(pal.Cyan, 0.03f, 0.45f, 3.5f);
      if (shellMat == null) { Destroy(shell); cv.Shell = null; }   // never leave a default silver sphere
      else { r.sharedMaterial = shellMat; JarvisSpatialGfx.Flat(r); cv.Shell = shell.transform; }
      cv.Label = MakeLabel(_graphRoot, cv.Name.ToUpperInvariant(), pal.TextMuted, LabelSize * 0.9f, Vector3.zero);
      return cv;
    }

    /// <summary>Build every pending member of an opened cluster, then wire up edges.</summary>
    private void MaterializeCluster(ClusterView cv)
    {
      var made = new List<NodeView>();
      foreach (var dto in cv.Pending)
      {
        if (_layout.TryGetValue(dto.id, out Vector3 pos)) made.Add(CreateNodeView(dto, cv, pos));
      }
      cv.Pending.Clear();
      foreach (var nv in made) TryCreateEdges(nv.Dto.id);
      TouchCluster(cv.Name);
      if (IsDesignGraph()) ApplyCompareColors();
      _lodList = new List<NodeView>(_nodes.Values);
      EnforceNodeBudget(cv.Name);
    }

    private void TouchCluster(string name)
    {
      _clusterLru.Remove(name);
      _clusterLru.AddLast(name);
    }

    // Over budget: close the least recently opened clusters, keeping their data so they can reopen.
    private void EnforceNodeBudget(string keep)
    {
      bool closed = false;
      while (_nodes.Count > MaxVisibleNodes && _clusterLru.Count > 1)
      {
        string oldest = _clusterLru.First.Value;
        if (oldest == keep) { _clusterLru.RemoveFirst(); _clusterLru.AddLast(oldest); continue; }
        _clusterLru.RemoveFirst();
        if (_clusters.TryGetValue(oldest, out var cv)) { DematerializeCluster(cv); closed = true; }
      }
      if (closed) Say("Limit reached: closed the oldest cluster. Filter or search to focus.");
    }

    private void DematerializeCluster(ClusterView cv)
    {
      var gone = new HashSet<NodeView>();
      for (int i = 1; i < cv.Members.Count; i++) gone.Add(cv.Members[i]);   // member 0 stays as the anchor
      _edges.RemoveAll(e =>
      {
        bool hit = gone.Contains(e.From) || gone.Contains(e.To);
        if (hit) { _edgeKeys.Remove(EdgeKey(e.Dto)); if (e.Line != null) Destroy(e.Line.gameObject); }
        return hit;
      });
      foreach (var nv in gone)
      {
        _nodes.Remove(nv.Dto.id);
        cv.Pending.Add(nv.Dto);
        Destroy(nv.Root.gameObject);
      }
      cv.Members.RemoveRange(1, cv.Members.Count - 1);
      cv.Collapsed = true;
      _lodList = new List<NodeView>(_nodes.Values);
      _edgesDirty = true;
    }

    /// <summary>Make sure a node that was never built now exists (select, search, agent ids).</summary>
    private bool EnsureNode(string id)
    {
      if (_nodes.ContainsKey(id)) return true;
      if (!_dtoById.TryGetValue(id, out var dto)) return false;
      string c = string.IsNullOrEmpty(dto.cluster) ? "other" : dto.cluster;
      if (!_clusters.TryGetValue(c, out var cv)) return false;
      SetClusterCollapsed(cv, false);
      return _nodes.ContainsKey(id);
    }

    // =========================================================== append instead of rebuild

    /// <summary>Merge a fetched neighbourhood into the live graph without rebuilding the scene.</summary>
    private void AppendGraph(GraphDto extra)
    {
      if (extra == null || extra.nodes == null) return;
      if (_graph.nodes == null) _graph.nodes = new List<GraphNodeDto>();
      if (_graph.edges == null) _graph.edges = new List<GraphEdgeDto>();
      var added = new Dictionary<string, List<GraphNodeDto>>();
      foreach (var n in extra.nodes)
      {
        if (_dtoById.ContainsKey(n.id)) continue;
        _graph.nodes.Add(n); _dtoById[n.id] = n;
        string c = string.IsNullOrEmpty(n.cluster) ? "other" : n.cluster;
        if (!added.TryGetValue(c, out var l)) added[c] = l = new List<GraphNodeDto>();
        l.Add(n);
      }
      int newEdges = 0;
      if (extra.edges != null)
        foreach (var e in extra.edges)
        {
          if (e == null || string.IsNullOrEmpty(e.src) || string.IsNullOrEmpty(e.dst)) continue;
          if (_edgeKeys.Contains(EdgeKey(e)) ||
              (_edgesByNode.TryGetValue(e.src, out var ex) && ex.Exists(x => EdgeKey(x) == EdgeKey(e)))) continue;
          _graph.edges.Add(e); AddEdgeIndex(e.src, e); AddEdgeIndex(e.dst, e); newEdges++;
        }
      if (added.Count == 0 && newEdges == 0) { Say("Nothing more to expand here."); return; }
      foreach (var kv in added)
      {
        ClusterView cv = GetOrCreateCluster(kv.Key);
        string anchor = cv.Members.Count > 0 ? cv.Members[0].Dto.id : kv.Value[0].id;
        LayoutAdd(_layout, anchor, kv.Value, cv.Members.Count + cv.Pending.Count);
        cv.Pending.AddRange(kv.Value);
        if (!cv.Collapsed) MaterializeCluster(cv);
      }
      foreach (var nv in new List<NodeView>(_nodes.Values)) TryCreateEdges(nv.Dto.id);
      UpdateClusters();
      RefreshEdgeVisibility();
      Log("expanded: +" + extra.nodes.Count + " nodes");
    }

    /// <summary>Stable placement for new nodes: earlier nodes never move.</summary>
    private static void LayoutAdd(Dictionary<string, Vector3> layout, string anchorId, IList<GraphNodeDto> add, int existing)
    {
      Vector3 anchor = layout.TryGetValue(anchorId, out Vector3 a) ? a : Vector3.zero;
      for (int i = 0; i < add.Count; i++)
      {
        float k = existing + i, r = 0.10f + 0.035f * Mathf.Sqrt(k), ang = k * 2.39996f;
        layout[add[i].id] = anchor + new Vector3(Mathf.Cos(ang) * r, Mathf.Sin(ang) * r, ((int)k % 5 - 2) * 0.03f);
      }
    }

    // =========================================================== cluster paging

    private void FetchClusterPage(string cluster, int offset)
    {
      _bridge.GetGraphCluster(cluster, offset, 800, g =>
      {
        if (g == null || g.nodes == null) return;
        _clusterNext[cluster] = g.next_offset;
        AppendGraph(g);
        Say(g.next_offset > 0
          ? "Loaded " + (offset + g.nodes.Count) + " of " + g.total_nodes + " in " + cluster + ". Press MORE for the next page."
          : "Loaded all " + g.total_nodes + " nodes in " + cluster + ".");
      }, e => Say("Could not load cluster: " + e));
    }

    private void LoadMoreSelectedCluster()
    {
      if (!_nodes.TryGetValue(_selected ?? "", out NodeView n)) { Say("Select a node first."); return; }
      if (_clusterNext.TryGetValue(n.Cluster.Name, out int next) && next > 0) FetchClusterPage(n.Cluster.Name, next);
      else Say("Nothing more to load for this cluster.");
    }

    // =========================================================== search jump

    private void GraphSearchSubmit(string text)
    {
      if (string.IsNullOrEmpty(text)) { Say("Nothing to search for."); return; }
      _bridge.SearchGraph(text, r =>
      {
        if (r == null || r.matches == null || r.matches.Length == 0) { Say("No match for " + text); return; }
        string id = r.matches[0].id;
        if (_nodes.ContainsKey(id)) { Select(id); return; }
        _bridge.GetGraphWithFocus(id, 2, g =>
        {
          if (g != null && g.nodes != null) AppendGraph(g);
          if (EnsureNode(id)) Select(id);
          else Say("Found " + id + " but could not load it.");
        }, e => Say("Could not load " + id + ": " + e));
      }, e => Say("Search failed: " + e));
    }

    // =========================================================== edge budget + redraw

    private void RefreshEdgeVisibility()
    {
      var show = new List<EdgeView>();
      foreach (EdgeView e in _edges)
      {
        if (e.Line == null) continue;
        e.Line.gameObject.SetActive(false);
        if (e.From.Fx.Shown && e.To.Fx.Shown && EdgePasses(e.Dto)) show.Add(e);
      }
      if (show.Count > MaxVisibleEdges) show.Sort((x, y) => EdgeRank(x).CompareTo(EdgeRank(y)));
      for (int i = 0; i < show.Count && i < MaxVisibleEdges; i++) show[i].Line.gameObject.SetActive(true);
      _edgesDirty = true;
    }

    private int EdgeRank(EdgeView e)   // lower is kept first: edges of the selected node, then confirmed ones
      => (e.Dto.src == _selected || e.Dto.dst == _selected ? 0 : 2) + (e.Dto.kind == "confirmed" ? 0 : 1);

    private static readonly Vector3[] _edgeBuf = new Vector3[9];

    private void RedrawEdges()
    {
      const int N = 8;
      foreach (EdgeView ev in _edges)
      {
        if (ev.Line == null || !ev.Line.gameObject.activeSelf) continue;
        Vector3 a = ev.From.Root.localPosition, b = ev.To.Root.localPosition;
        float d = Vector3.Distance(a, b);
        Vector3 mid = (a + b) * 0.5f + new Vector3(0f, 0.04f + 0.10f * d, -0.10f * d);
        for (int i = 0; i <= N; i++)
        {
          float t = i / (float)N, u = 1f - t;
          _edgeBuf[i] = u * u * a + 2f * u * t * mid + t * t * b;
        }
        ev.Line.positionCount = N + 1;
        ev.Line.SetPositions(_edgeBuf);
      }
      _edgesDirty = false;
    }

    // =========================================================== label LOD

    /// <summary>Labels only near the headset (or on the selected node); 200 nodes per frame, round robin.</summary>
    private void UpdateLabelLod()
    {
      if (_lodList.Count == 0) return;
      Vector3 head = _cam != null ? _cam.transform.position : Vector3.zero;
      const float R2 = 2.5f * 2.5f;
      int n = Mathf.Min(200, _lodList.Count);
      for (int k = 0; k < n; k++)
      {
        _lodCursor = (_lodCursor + 1) % _lodList.Count;
        NodeView nv = _lodList[_lodCursor];
        if (nv.Root == null || nv.Label == null || !nv.Fx.Shown) continue;
        bool near = nv.Dto.id == _selected || (nv.Root.position - head).sqrMagnitude < R2;
        if (nv.Label.gameObject.activeSelf != near) nv.Label.gameObject.SetActive(near);
      }
    }

    // =========================================================== scale self-test

    /// <summary>Build a synthetic graph of <paramref name="clusters"/> x <paramref name="perCluster"/>
    /// nodes, load it, expand every cluster and log build time plus average frame time.</summary>
    public void DebugLoadSynthetic(int clusters, int perCluster)
    {
      var g = new GraphDto();
      for (int c = 0; c < clusters; c++)
      {
        string cl = "syn" + c;
        string prev = null;
        for (int i = 0; i < perCluster; i++)
        {
          string id = cl + "::n" + i;
          g.nodes.Add(new GraphNodeDto
          {
            id = id, name = "n" + i, kind = "function", level = "function",
            cluster = cl, file = cl + "/f" + i + ".ts", start = 1, end = 5,
          });
          if (prev != null) g.edges.Add(new GraphEdgeDto { src = prev, dst = id, type = "calls", kind = "confirmed" });
          prev = id;
        }
      }
      float t0 = Time.realtimeSinceStartup;
      LoadGraph(g);
      float buildMs = (Time.realtimeSinceStartup - t0) * 1000f;
      StartCoroutine(SyntheticMeasure(buildMs));
    }

    private IEnumerator SyntheticMeasure(float buildMs)
    {
      foreach (ClusterView cv in new List<ClusterView>(_clusters.Values)) SetClusterCollapsed(cv, false);
      float sum = 0f;
      for (int i = 0; i < 120; i++) { yield return null; sum += Time.unscaledDeltaTime; }
      Debug.Log("[JARVIS Scale] synthetic build " + buildMs.ToString("F0") + "ms | shown " + _nodes.Count +
        " loaded " + _dtoById.Count + " | edges " + _edges.Count +
        " | avg frame " + (sum / 120f * 1000f).ToString("F1") + "ms");
    }
  }
}
