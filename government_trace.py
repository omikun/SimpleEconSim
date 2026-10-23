"""Record shared-government policy writes at their actual mutation point."""
def tax_rate_change(region,government,before,*,reason,formula,inputs):
    from run_trace import emit
    nation=getattr(region,'owner_nation',None)
    aliases=[tile for tile in getattr(nation,'tiles',()) if getattr(tile,'gov',None) is government]
    if region not in aliases:aliases.append(region)
    for tile in aliases:
        emit(tile,kind='government_tax_policy_write',record_class='outcome',
             subject={'type':'tile','id':tile.name},metric_id='finance.tax_rate',unit='ratio',
             before=before,after=float(government.tax_rate),formula_id=formula,
             inputs={'reason':reason,'source_tile':region.name,'government':government.name,
                     'government_id':government.agent.id,'shared_alias_tiles':[item.name for item in aliases],**inputs})
