Shader "JARVIS/FresnelShell"
{
  Properties
  {
    _Color ("Color", Color) = (0.37, 0.88, 1, 1)
    _Fill ("Fill alpha", Range(0, 1)) = 0.08
    _Rim ("Rim alpha", Range(0, 1)) = 0.85
    _Power ("Rim power", Range(0.5, 8)) = 3
  }
  SubShader
  {
    Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
    Pass
    {
      Name "Forward"
      Tags { "LightMode" = "UniversalForward" }
      Blend SrcAlpha OneMinusSrcAlpha
      ZWrite Off
      Cull Back

      HLSLPROGRAM
      #pragma vertex vert
      #pragma fragment frag
      #pragma multi_compile_instancing
      #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

      CBUFFER_START(UnityPerMaterial)
        float4 _Color;
        float _Fill;
        float _Rim;
        float _Power;
      CBUFFER_END

      struct Attributes
      {
        float4 positionOS : POSITION;
        float3 normalOS : NORMAL;
        UNITY_VERTEX_INPUT_INSTANCE_ID
      };

      struct Varyings
      {
        float4 positionCS : SV_POSITION;
        float3 normalWS : TEXCOORD0;
        float3 viewWS : TEXCOORD1;
        UNITY_VERTEX_INPUT_INSTANCE_ID
        UNITY_VERTEX_OUTPUT_STEREO
      };

      Varyings vert(Attributes i)
      {
        Varyings o;
        UNITY_SETUP_INSTANCE_ID(i);
        UNITY_TRANSFER_INSTANCE_ID(i, o);
        UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
        VertexPositionInputs p = GetVertexPositionInputs(i.positionOS.xyz);
        o.positionCS = p.positionCS;
        o.normalWS = TransformObjectToWorldNormal(i.normalOS);
        o.viewWS = GetWorldSpaceViewDir(p.positionWS);
        return o;
      }

      half4 frag(Varyings i) : SV_Target
      {
        UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
        float3 n = normalize(i.normalWS);
        float3 v = normalize(i.viewWS);
        float fres = pow(1.0 - saturate(dot(n, v)), _Power);
        return half4(_Color.rgb, saturate(_Fill + fres * _Rim));
      }
      ENDHLSL
    }
  }
}
