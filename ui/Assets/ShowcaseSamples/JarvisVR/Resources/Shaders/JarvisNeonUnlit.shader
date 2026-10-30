Shader "JARVIS/NeonUnlit"
{
  Properties
  {
    _MainTex ("Texture", 2D) = "white" {}
    _Color ("Color", Color) = (1, 1, 1, 1)
    _Intensity ("HDR intensity (feeds Bloom)", Range(0, 6)) = 1.6
    [HideInInspector] _ZWrite ("ZWrite", Float) = 0
  }
  SubShader
  {
    Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
    Pass
    {
      Name "Forward"
      Tags { "LightMode" = "UniversalForward" }
      Blend SrcAlpha OneMinusSrcAlpha
      ZWrite [_ZWrite]
      Cull Off

      HLSLPROGRAM
      #pragma vertex vert
      #pragma fragment frag
      #pragma multi_compile_instancing
      #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

      TEXTURE2D(_MainTex);
      SAMPLER(sampler_MainTex);

      CBUFFER_START(UnityPerMaterial)
        float4 _MainTex_ST;
        float4 _Color;
        float _Intensity;
      CBUFFER_END

      struct Attributes
      {
        float4 positionOS : POSITION;
        float2 uv : TEXCOORD0;
        float4 color : COLOR;
        UNITY_VERTEX_INPUT_INSTANCE_ID
      };

      struct Varyings
      {
        float4 positionCS : SV_POSITION;
        float2 uv : TEXCOORD0;
        float4 color : COLOR;
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
        o.uv = TRANSFORM_TEX(i.uv, _MainTex);
        o.color = i.color;
        return o;
      }

      half4 frag(Varyings i) : SV_Target
      {
        UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
        half4 t = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
        half4 c = t * i.color * _Color;
        c.rgb *= _Intensity;
        return c;
      }
      ENDHLSL
    }
  }
}
