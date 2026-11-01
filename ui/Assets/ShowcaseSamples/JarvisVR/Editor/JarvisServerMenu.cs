#if UNITY_EDITOR
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

namespace JarvisVR.EditorTools
{
  /// <summary>JARVIS > Server menu: edit the connection settings and test the connection without leaving the Editor.</summary>
  public static class JarvisServerMenu
  {
    private const string AssetPath = "Assets/ShowcaseSamples/JarvisVR/Resources/JarvisServerSettings.asset";

    private static JarvisServerSettings Load()
    {
      var s = AssetDatabase.LoadAssetAtPath<JarvisServerSettings>(AssetPath);
      if (s == null)
      {
        s = ScriptableObject.CreateInstance<JarvisServerSettings>();
        AssetDatabase.CreateAsset(s, AssetPath);
        AssetDatabase.SaveAssets();
      }
      return s;
    }

    private static void Save(JarvisServerSettings s) { EditorUtility.SetDirty(s); AssetDatabase.SaveAssets(); }

    [MenuItem("JARVIS/Server/Open settings asset")]
    private static void Open() { var s = Load(); Selection.activeObject = s; EditorGUIUtility.PingObject(s); }

    [MenuItem("JARVIS/Server/Use this computer (Editor, XR Simulator)")]
    private static void UseLocal()
    {
      var s = Load(); s.ServerUrl = "http://127.0.0.1:8000"; Save(s);
      PlayerPrefs.DeleteKey("jarvis.server"); PlayerPrefs.Save();   // an old PlayerPrefs override would win over the asset
      Debug.Log("JARVIS: server URL = " + s.ServerUrl);
    }

    [MenuItem("JARVIS/Server/Use this computer's LAN IP (for Quest)")]
    private static void UseLan()
    {
      string ip = LanIp();
      if (ip == null) { Debug.LogError("JARVIS: no LAN address found. Type the URL into the settings asset by hand."); return; }
      var s = Load(); s.ServerUrl = "http://" + ip + ":8000"; Save(s);
      PlayerPrefs.DeleteKey("jarvis.server"); PlayerPrefs.Save();
      Debug.Log("JARVIS: server URL = " + s.ServerUrl + "  (the headset must be on the same Wi-Fi; start the server with --host 0.0.0.0)");
    }

    [MenuItem("JARVIS/Server/Generate a new token")]
    private static void NewToken()
    {
      var s = Load(); s.Token = System.Guid.NewGuid().ToString("N"); Save(s);
      PlayerPrefs.DeleteKey("jarvis.token"); PlayerPrefs.Save();
      Debug.Log("JARVIS: new token saved in the settings asset. Start the server with:\n  export JARVIS_TOKEN=" + s.Token);
    }

    [MenuItem("JARVIS/Server/Test connection")]
    private static void Test()
    {
      string url = JarvisBridge.ResolveUrl(), token = JarvisBridge.ResolveToken();
      var health = UnityWebRequest.Get(url + "/health");
      var graph = UnityWebRequest.Get(url + "/graph");
      if (!string.IsNullOrEmpty(token)) graph.SetRequestHeader("Authorization", "Bearer " + token);
      health.timeout = 8; graph.timeout = 8;
      health.SendWebRequest(); graph.SendWebRequest();
      Debug.Log("JARVIS: testing " + url + " ...");
      void Poll()
      {
        if (!health.isDone || !graph.isDone) return;
        EditorApplication.update -= Poll;
        if (health.result != UnityWebRequest.Result.Success)
          Debug.LogError("JARVIS: cannot reach " + url + " (" + health.error + "). Is the server running? From a Quest use the computer's LAN IP, same Wi-Fi, and start uvicorn with --host 0.0.0.0.");
        else if (graph.responseCode == 401)
          Debug.LogError("JARVIS: server reachable, but it rejected the token. JarvisServerSettings.Token must equal JARVIS_TOKEN on the server.");
        else if (graph.result != UnityWebRequest.Result.Success)
          Debug.LogError("JARVIS: server reachable, /graph failed: " + graph.error + " " + graph.downloadHandler.text);
        else
        {
          var h = JsonUtility.FromJson<HealthDto>(health.downloadHandler.text);
          var g = JsonUtility.FromJson<GraphDto>(graph.downloadHandler.text);
          Debug.Log("JARVIS: CONNECTED to " + url + "  repo=" + h.repo + "  branch=" + h.branch + "  graph=" + g.nodes.Count + " nodes, " + g.edges.Count + " edges");
        }
        health.Dispose(); graph.Dispose();
      }
      EditorApplication.update += Poll;
    }

    private static string LanIp()
    {
      foreach (var ni in NetworkInterface.GetAllNetworkInterfaces())
      {
        if (ni.OperationalStatus != OperationalStatus.Up) continue;
        if (ni.NetworkInterfaceType != NetworkInterfaceType.Wireless80211 && ni.NetworkInterfaceType != NetworkInterfaceType.Ethernet) continue;
        foreach (var ua in ni.GetIPProperties().UnicastAddresses)
        {
          if (ua.Address.AddressFamily != AddressFamily.InterNetwork || IPAddress.IsLoopback(ua.Address)) continue;
          string a = ua.Address.ToString();
          if (!a.StartsWith("169.254")) return a;
        }
      }
      return null;
    }
  }
}
#endif