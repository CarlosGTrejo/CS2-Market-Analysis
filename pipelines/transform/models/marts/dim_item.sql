with stg_items as (
    select
        item_name,
        class_id,
        bucket_group_id,
        bucket_group_name,
        item_type,
        name_color,
        is_tradable,
        is_commodity,
        snapshot_date
    from {{ ref('stg_items') }}
    
    {% if is_incremental() %}
        where snapshot_date >= (select max(updated_at) from {{ this }})
    {% endif %}
),

deduplicated_items as (
    select 
        * except(snapshot_date),
        snapshot_date as updated_at
    from stg_items
    qualify row_number() over (
        partition by item_name 
        order by snapshot_date desc
    ) = 1
)

select * from deduplicated_items