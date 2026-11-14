"""Generic academic labels and conservative name handling, not saved pages."""
import re
import unicodedata
from difflib import SequenceMatcher

TERMS={
    'universidad':'trường đại học',
    'otorga a':'Trao cho','otorga':'Trao','el título de':'Bằng',
    'química bióloga clínica':'Hóa sinh lâm sàng','mención honorífica':'Khen thưởng danh dự',
    'del programa de':'Trong chương trình','rector':'Hiệu trưởng','rectora':'Hiệu trưởng',
    'secretaria general administrativa':'Tổng thư ký hành chính',
    'secretario general administrativo':'Tổng thư ký hành chính',
    'vicerrectora':'Phó hiệu trưởng','vicerrector':'Phó hiệu trưởng',
    'unidad regional centro':'Phân hiệu khu vực Trung tâm',
    'firma del interesado':'Chữ ký người được cấp',
    'confers upon':'Trao cho','the bachelor\'s degree of':'Bằng cử nhân ngành',
    'clinical chemist biologist':'Hóa sinh lâm sàng','cum laude':'Tốt nghiệp loại giỏi',
    'the bachelor\'s degree program of':'Chương trình cử nhân ngành',
    'scholastic services':'Phòng quản lý đào tạo','academic record':'Bảng kết quả học tập',
}


def bare(word):
    return ''.join(c for c in unicodedata.normalize('NFD',word.casefold()) if unicodedata.category(c)!='Mn')


def is_academic(item):
    text=' '.join(b['text'] for p in item['pages'] for b in p['blocks']).casefold()
    return any(t in text for t in ('univers','univer','bachelor','química','quimica','degree','título','titulo'))


def normalize(text,source):
    text=text.replace('’',"'")
    labels=('universidad','otorga','química','bióloga','clínica','rector','rectora') if source=='es' else ('universidad','degree','university')
    def correct(match):
        word=match.group();plain=bare(word)
        for label in labels:
            expected=bare(label)
            threshold=.68 if label=='universidad' and ('niver' in plain or plain.startswith('untver')) else .82
            if len(word)>=5 and SequenceMatcher(None,plain,expected).ratio()>=threshold:
                return label.capitalize() if word[0].isupper() else label
        return word
    text=re.sub(r'[^\W\d_]+',correct,text)
    text=re.sub(r'(Universidad)\s+(?:he|ve)\s+',r'\1 de ',text,flags=re.I)
    return text


def named_field(text):
    institution=re.fullmatch(r'(?:(?:la|the|a|e|pp|p)\s+)?universidad\s+(?:de\s+)?([\wÀ-ž\s-]{2,65})[.,]?',text.strip(),re.I)
    if institution and len(institution[1].split())<=6:
        return 'Đại học '+institution[1].strip(),'institution'
    cleaned=re.sub(r'^(?:Dr\.|Dra\.|M\.E\.|M\.C\.)\s*','',text.strip())
    words=re.findall(r'[A-Za-zÀ-ž]+',cleaned)
    blocked={'university','universidad','clinical','chemist','biologist','bachelor','degree','mención','honorífica','secretaria','secretario','general','administrativa','administrativo'}
    if 3<=len(words)<=7 and not any(w.casefold() in blocked for w in words) and all(w[0].isupper() and any(c.islower() for c in w[1:]) for w in words):
        # Personal names keep their spelling, with a readable re-rendering.
        return text.strip(),'proper_name'
    return None
