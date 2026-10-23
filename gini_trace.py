"""Capture cash-Gini inputs where the native history is actually written."""
def record_sample(region,group,good,turn,history,*,series_name=None):
    if getattr(region,'_run_trace',None) is None:return
    from run_trace import emit
    name=series_name or getattr(good,'name',str(good))
    before=history[-2] if len(history)>1 else None
    if turn%10==0:
        members=sorted(({'agent_id':str(person.id),'cash':float(person.cash)}
                        for person in group if person.output==good),key=lambda row:(row['cash'],row['agent_id']))
        formula='gini.cash_by_output.v1'
        inputs={'members_sorted_by_cash':members,'sample_point':'native_local_history_write',
                'refresh_interval_turns':10,'recomputed_this_turn':True,'output_good':name}
    else:
        formula='gini.retain_previous_value.v1'
        inputs={'previous_gini':before if before is not None else 0,
                'sample_point':'native_local_history_write','recomputed_this_turn':False,
                'refresh_interval_turns':10,'initial_empty_series':before is None,'output_good':name}
    sources=getattr(region,'_trace_gini_sources',{})
    event=emit(region,kind='gini_series_calculation',record_class='calculation',
               subject={'type':'tile','id':region.name,'good':name},metric_id='economy.gini',unit='ratio',
               before=before,after=history[-1],formula_id=formula,inputs=inputs,
               cause_event_ids=[sources[name]] if name in sources else None)
    if event is not None:
        sources[name]=event;region._trace_gini_sources=sources
