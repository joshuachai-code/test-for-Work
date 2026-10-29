from datetime import date,timedelta

def summarize(rows,today,period='all',warning_days=7):
    start=today.replace(day=1) if period=='month' else today-timedelta(days=29) if period=='30' else date.min
    groups={'CTC':{'category':'CTC','billed_sen':0,'pending':0,'completed':0}}
    attention={'overdue':0,'due_soon':0,'undated':0,'awaiting_review':0,'awaiting_approval':0,'awaiting_invoice':0,'unbilled_sen':0}
    for p in rows:
        g=groups.setdefault(p['subcategory'],{'category':p['subcategory'],'billed_sen':0,'pending':0,'completed':0})
        if p['work_status']!='completed':
            g['pending']+=1
            if p.get('due_date'):
                due=date.fromisoformat(p['due_date'])
                if due<today:attention['overdue']+=1
                elif due<=today+timedelta(days=warning_days):attention['due_soon']+=1
            else:attention['undated']+=1
            if p.get('workflow_stage')=='review':attention['awaiting_review']+=1
            if p.get('workflow_stage')=='approval':attention['awaiting_approval']+=1
        if p['work_status']=='completed' and start<=date.fromisoformat(p['completed_date'])<=today:g['completed']+=1
        if p.get('billing_status')=='issued' and start<=date.fromisoformat(p['invoice_date'])<=today:g['billed_sen']+=p['billed_sen']
        if p.get('billing_status','pending')=='pending':
            if p['work_status']=='completed':attention['awaiting_invoice']+=1
            attention['unbilled_sen']+=p.get('charge_sen',0)
    return {'categories':list(groups.values()),'attention':attention,'warning_days':warning_days}
