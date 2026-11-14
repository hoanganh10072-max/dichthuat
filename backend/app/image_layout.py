"""Tesseract line boxes for deterministic translated-image rendering."""
from collections import OrderedDict


def line_regions(data):
    lines = OrderedDict()
    for i, word in enumerate(data['text']):
        if not word.strip() or float(data['conf'][i]) < 0:
            continue
        key = tuple(data[field][i] for field in ('page_num', 'block_num', 'par_num', 'line_num'))
        x, y, w, h = (int(data[field][i]) for field in ('left', 'top', 'width', 'height'))
        item = lines.setdefault(key, {'words': [], 'x': x, 'y': y, 'right': x + w, 'bottom': y + h})
        item['words'].append(word.strip())
        item['x'], item['y'] = min(item['x'], x), min(item['y'], y)
        item['right'], item['bottom'] = max(item['right'], x + w), max(item['bottom'], y + h)
    return [{'text': ' '.join(item['words']), 'x': item['x'], 'y': item['y'],
             'width': item['right'] - item['x'], 'height': item['bottom'] - item['y']}
            for item in lines.values()]
