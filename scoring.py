import hashlib
import json


def get_score(store, phone, email, birthday=None, gender=None, first_name=None, last_name=None):
    key_parts = [
        first_name or '',
        last_name or '',
        birthday if birthday is not None else "",
    ]
    key = 'uid:' + hashlib.md5(''.join(key_parts).encode('utf-8')).hexdigest()
    score = store.cache_get(key) or 0
    score = float(score)
    if phone:
        score += 1.5
    if email:
        score += 1.5
    if birthday and gender:
        score += 1.5
    if first_name and last_name:
        score += 0.5
    store.cache_set(key, score, 60 * 60)
    return score


def get_interests(store, cid):
    req = store.get(f'i:{cid}')
    return json.loads(req) if req else []
