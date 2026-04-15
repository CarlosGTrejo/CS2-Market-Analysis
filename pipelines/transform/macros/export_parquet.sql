{% macro export_parquet() %}
  {%- set project = env_var('GOOGLE_CLOUD_PROJECT') -%}
  {%- set stack = env_var('PULUMI_STACK', 'dev') -%}
  {%- set bucket_name = project ~ "-cs2-data-lake-" ~ stack -%}
  
  EXPORT DATA OPTIONS(
    uri='gs://{{ bucket_name }}/dashboard-exports/{{ this.identifier }}/*.parquet',
    format='PARQUET',
    overwrite=true
  ) AS
  SELECT * FROM {{ this }}
{% endmacro %}