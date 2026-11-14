"""Choose layout fidelity only when all translated text remains readable."""
PDF_FORM_LANGUAGES=frozenset(('vi','en','fr','de','es','id','ms','ru','it','pt','nl'))
MIN_READABLE_PT=9


def document_output_policy(item):
    if item.get('target') not in PDF_FORM_LANGUAGES:
        return {'mode':'a4','reason':'Chọn Word A4 để dàn chữ của ngôn ngữ này ổn định.','min_font_pt':None}
    if item.get('overflow_count',0):
        return {'mode':'a4','reason':'Bản dịch dài hơn khung gốc.','min_font_pt':None}
    sizes=[b.get('layout',{}).get('font_size',b.get('font_size',0))
        for p in item['pages'] for b in p['blocks'] if not b.get('keep') and b.get('translation','').strip()]
    smallest=min(sizes,default=0)
    if smallest<MIN_READABLE_PT:
        return {'mode':'a4','reason':'Giữ form gốc sẽ làm chữ quá nhỏ.','min_font_pt':round(smallest,2) if smallest else None}
    return {'mode':'original','reason':'Bản dịch vừa khung và cỡ chữ đủ rõ.','min_font_pt':round(smallest,2)}
