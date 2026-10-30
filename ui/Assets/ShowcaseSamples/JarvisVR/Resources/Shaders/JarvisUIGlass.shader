Shader "JARVIS/UIGlass"
{
  // Panel background for world-space UGUI Images. Rounded-rect SDF gives a crisp edge and an HDR rim glow (feeds Bloom).
  // With _REFRACT on (URP asset > Opaque Texture enabled) it also samples the scene behind the panel with a small blur and
  // an edge-weighted offset, which reads as thick glass. With _REFRACT off it is a smoked, tinted pane: no extra cost.
  Properties
  {
    [HideInInspector] _MainTex ("Sprite", 2D) = "white" {}
    _Tint ("Glass tint (rgb), body alpha (a)", Color) = (0.04, 0.07, 0.12, 0.62)
    _EdgeColor ("Edge glow color", Color) = (0.2, 0.9, 1, 1)
    _EdgeGlow ("Edge glow (HDR)", Range(0, 4)) = 1.4
    _EdgeWidth ("Edge falloff (px)", Range(2, 80)) = 22
    _Size ("Panel size (px)", Vector) = (1000, 600, 0, 0)
    _Radius ("Corner radius (px)", Range(0, 80)) = 28
    _Distort ("Refraction strength", Range(0, 0.08)) = 0.02
    _Blur ("Blur radius (screen uv)", Range(0, 0.01)) = 0.003
    _Dim ("Backdrop brightness", Range(0, 1)) = 0.55
  }
  SubShader
  {
    Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
    Pass
    {
      Name "Forward"
      Tags { "LightMode" = "UniversalForward" }
      Blend SrcAlpha OneMinusSrcAlpha
      ZWrite Off
      ZTest LEqual
      Cull Off

      HLSLPROGRAM
      #pragma vertex vert
      #pragma fragment frag
      #pragma multi_compile_instancing
      #pragma multi_compile_local _ _REFRACT
      #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
      #if defined(_REFRACT)
      #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareOpaqueTexture.hlsl"
      #endif

      CBUFFER_START(UnityPerMaterial)
        half4 _Tint;
        half4 _EdgeColor;
        float4 _Size;
        float _EdgeGlow, _EdgeWidth, _Radius, _Distort, _Blur, _Dim;
      CBUFFER_END

      struct Attributes
      {
        float4 positionOS : POSITION;
        float4 color : COLOR;
        UNITY_VERTEX_INPUT_INSTANCE_ID
      };

      struct Varyings
      {
        float4 positionCS : SV_POSITION;
        float4 color : COLOR;
        float2 pos : TEXCOORD0;   // position inside the Image rect, in canvas pixels, centered
        UNITY_VERTEX_INPUT_INSTANCE_ID
        UNITY_VERTEX_OUTPUT_STEREO
      };

      Varyings vert(Attributes i)
      {
        Varyings o;
        UNITY_SETUP_INSTANCE_ID(i);
        UNITY_TRANSFER_INSTANCE_ID(i, o);
        UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
        o.positionCS = TransformObjectToHClip(i.positionOS.xyz);
        o.color = i.color;   // only alpha is used: the CanvasGroup fade arrives through it
        o.pos = i.positionOS.xy;
        return o;
      }

      half4 frag(Varyings i) : SV_Target
      {
        UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
        float2 q = abs(i.pos) - _Size.xy * 0.5 + _Radius;
        float sd = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - _Radius;   // < 0 inside the rounded rect
        float mask = saturate(0.5 - sd);                                        // 1 px anti-aliased edge
        float depth = max(-sd, 0.0);
        float edge = exp(-depth / max(_EdgeWidth, 0.001));

        half3 col = _Tint.rgb;
        half a = _Tint.a;
      #if defined(_REFRACT)
        float2 suv = GetNormalizedScreenSpaceUV(i.positionCS);
        float2 o = normalize(i.pos + 1e-3) * edge * _Distort;   // bend the backdrop outward near the rim
        half3 s = SampleSceneColor(suv + o).rgb;
        s += SampleSceneColor(suv + o + float2( _Blur, 0)).rgb;
        s += SampleSceneColor(suv + o + float2(-_Blur, 0)).rgb;
        s += SampleSceneColor(suv + o + float2(0,  _Blur)).rgb;
        s += SampleSceneColor(suv + o + float2(0, -_Blur)).rgb;
        col = s * 0.2 * _Dim + _Tint.rgb * _Tint.a;
        a = 0.96;
      #endif
        col += _EdgeColor.rgb * (edge * edge) * _EdgeGlow;
        half alpha = mask * saturate(a + edge * 0.3) * i.color.a;
        return half4(col, alpha);
      }
      ENDHLSL
    }
  }
}
