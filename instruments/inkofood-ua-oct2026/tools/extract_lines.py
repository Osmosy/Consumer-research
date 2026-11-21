import pymupdf, json
import os
PDF=os.environ.get("INKO_PDF","/home/lenovo/Загрузки/Маркетинговое исследование Инко Фуд, онлайн панель 900 респондентов.pdf")
d=pymupdf.open(PDF)
lines=[]
for i,p in enumerate(d):
    dd=p.get_text("dict")
    for b in dd["blocks"]:
        if b.get("type")!=0: continue
        for l in b["lines"]:
            txt="".join(s["text"] for s in l["spans"])
            if not txt.strip(): continue
            x0,y0,x1,y1=l["bbox"]
            fonts=sorted({f'{s["font"]}/{round(s["size"],1)}' for s in l["spans"]})
            lines.append({"page":i+1,"bbox":[round(v,2) for v in (x0,y0,x1,y1)],
                          "text":txt,"fonts":fonts})
print("lines:",len(lines))
bullets=sum(1 for l in lines if l["text"].strip().startswith("●"))
print("bullet lines:",bullets)
json.dump(lines,open("lines.json","w"),ensure_ascii=False,indent=0)
# font inventory
from collections import Counter
c=Counter(f for l in lines for f in l["fonts"])
for k,v in c.most_common(20): print(f"{v:5d}  {k}")
