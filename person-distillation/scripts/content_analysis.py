"""Typed source-based interpretation sections; this never generates prose."""
import copy

def sections(value):
    if value is None:return []
    if not isinstance(value,list):raise ValueError('analysis_sections must be a list')
    result=[]
    for original in value:
        if not isinstance(original,dict) or not isinstance(original.get('title'),str) or not original['title'].strip():
            raise ValueError('analysis_sections need specific titles')
        row=copy.deepcopy(original);body=row.get('paragraphs')
        if isinstance(body,str):body=[body]
        if not isinstance(body,list) or not body or any(not isinstance(p,str) or not p.strip() for p in body):
            raise ValueError('analysis_sections need nonempty explanatory paragraphs')
        if 'images' in row and (not isinstance(row['images'],list) or any(not isinstance(pic,dict) for pic in row['images'])):
            raise ValueError('analysis section images must be an object list')
        row['paragraphs']=body;result.append(row)
    return result

def text(value):
    return '\n\n'.join(row['title']+'\n'+'\n\n'.join(row['paragraphs']) for row in sections(value))
