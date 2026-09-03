#!/usr/bin/env python3
"""
ETL mapeo legacy -> catálogo para 10 dropdowns + No-Tarjeta
Reutiliza ticket_fields.json custom_field_options, no hardcodea frontend.
Mapea 41 huérfanos + X->null y dependencias Entidad->...->Otras
"""
import json, pathlib, re
from collections import Counter, defaultdict

BACKUP = pathlib.Path(r"C:\Users\Nicolas Chala\Product Owner - Soporte\zendesk-backup-silin\backups\2026-09-02_FULL_2026-09-02_08-56-26")
FIELDS_PATH = BACKUP / "json/ticket_fields.json"
TICKETS_PATH = BACKUP / "json/tickets.json"

# IDs de los 10 dropdowns + No-Tarjeta
FIELD_IDS = {
    "Tipo-Informe": 41302403884557,
    "Entidad": 11622270573837,
    "Tributo": 35139407697805,
    "Portal SILIN": 12491763418637,
    "TipoTicket Entidad SILIN": 11588515928205,
    "Tipo Solicitud Entidad SILIN": 11588303168525,
    "Otras Solicitudes": 38276732136461,
    "Nivel de Atención": 30920328139405,
    "Impacto": 11749979171469,
    "Urgencia": 11651783070477,  # obsoleto, mapear a Prioridad
    "Prioridad": 11393617430669, # sistema
    "No-Tarjeta": 30598614640397,
}

# Mapeo legado -> catálogo (41 huérfanos)
LEGACY_MAP = {
    # Entidad
    "gob-valle": "g-valle",
    "alc-valledupar": "a-valledupar",
    "alc-palmira": "a-palmira",
    "X": None,
    # Tributo
    "ica_reteica": "industrial_y_comercio",
    # TipoTicket
    "capacitación_asistencia_silin": "solicitud_silin",
    # Tipo Solicitud - 32 huérfanos
    "solicitud_de_información": "otras_solicitudes_",
    "envío_de_información_silin": "envío_de_información",
    "envio_de_informacion_silin": "envío_de_información",
    "olvido_de_contraseña": "otr_Solicitud -Olvido de Contraseña",
    "solicitud_de_cambio": "solicitud_mod_reportes_silin",
    "solicitud_de_facturación_silim": "solicitud_mod_facturación_silin",
    "solicitud_incremental": "solicitud_incremental",
    "parametrización": "parametrización",
    "capacitación_silin": "capacitación",
    "solicitud_mod_reportes_silin": "solicitud_mod_reportes_silin", # ya es catálogo, mantener
    # Otras - X ya
    # Nivel, Impacto X ya
}

# Normalización: lower, sin tildes para matching robusto
def norm(s):
    if not s: return ""
    import unicodedata
    s=s.lower().strip()
    s=unicodedata.normalize('NFD', s)
    s=''.join(c for c in s if unicodedata.category(c)!='Mn')
    return s

# Cargar fields
fields=json.load(open(FIELDS_PATH,encoding='utf-8'))
field_by_id={f['id']:f for f in fields}
field_by_title={f['title'].strip():f for f in fields}

print(f"Fields total {len(fields)}")
for name, fid in FIELD_IDS.items():
    f=field_by_id.get(fid)
    if f:
        opts=len(f.get('custom_field_options',[]) or f.get('system_field_options',[]) or [])
        print(f"{name:30} id {fid} type {f['type']:12} opts {opts} active {f.get('active')}")
    else:
        print(f"{name:30} NOT FOUND id {fid}")

# Analizar tickets custom_fields
tickets=json.load(open(TICKETS_PATH,encoding='utf-8'))
print(f"\nTickets {len(tickets)}")

# Contar valores por campo
field_value_counts=defaultdict(Counter)
field_null_counts=defaultdict(int)
for t in tickets:
    cf_map={cf['id']:cf.get('value') for cf in t.get('custom_fields',[])}
    for name, fid in FIELD_IDS.items():
        val=cf_map.get(fid)
        if val is None or val=="":
            field_null_counts[name]+=1
        else:
            field_value_counts[name][val]+=1

for name in FIELD_IDS:
    cnt=field_value_counts[name]
    nulls=field_null_counts[name]
    print(f"\n{name}: null={nulls} distinct={len(cnt)} total_fill={sum(cnt.values())}")
    for val, c in cnt.most_common(5):
        print(f"  {val!r:40} {c}")

# Detectar huérfanos vs catálogo
print("\n=== HUERFANOS ===")
for name, fid in FIELD_IDS.items():
    f=field_by_id.get(fid)
    if not f: continue
    catalog=set(opt['value'] for opt in (f.get('custom_field_options') or f.get('system_field_options') or []))
    used=set(field_value_counts[name].keys())
    orphans=used - catalog
    if orphans:
        print(f"{name}: orphans {orphans} (catalog {len(catalog)} used {len(used)})")
        for o in list(orphans)[:5]:
            print(f"  orphan {o!r} -> map {LEGACY_MAP.get(o, '-> null' if o=='X' else 'manual') } count {field_value_counts[name][o]}")

# Generar mapping_report
report={
    "field_ids": FIELD_IDS,
    "legacy_map": LEGACY_MAP,
    "field_stats": {name: {"null": field_null_counts[name], "distinct": len(field_value_counts[name]), "fill": sum(field_value_counts[name].values()), "top": field_value_counts[name].most_common(3)} for name in FIELD_IDS},
}
# Guardar
out=BACKUP / "mapping_report.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\nReport guardado {out}")

# Aplicar mapeo a tickets y generar tickets_mapped.json + actualizar DB si existe
mapped_count=0
for t in tickets:
    for cf in t.get('custom_fields',[]):
        fid=cf['id']
        # encontrar nombre por fid
        name=None
        for n, f in FIELD_IDS.items():
            if f==fid:
                name=n
                break
        if not name:
            continue
        val=cf.get('value')
        if val in LEGACY_MAP:
            new_val=LEGACY_MAP[val]
            if new_val != val:
                cf['value']=new_val
                mapped_count+=1
        # también normalizar X
        if val=="X":
            cf['value']=None
            mapped_count+=1

print(f"Mapeados {mapped_count} custom_fields")

# Guardar tickets_mapped.json (solo si cambió)
out_mapped=BACKUP / "json/tickets_mapped.json"
out_mapped.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Tickets mapeados guardado {out_mapped} {out_mapped.stat().st_size/1024/1024:.1f} MB")

# Actualizar DB zendesk_clone.db si existe
import pathlib as pl
db_path=pl.Path(r"C:\Users\Nicolas Chala\Product Owner - Soporte\zendesk-clone\zendesk_clone.db")
if db_path.exists():
    print(f"\nActualizando DB {db_path} ...")
    import sqlite3, json as js
    con=sqlite3.connect(str(db_path))
    cur=con.cursor()
    # actualizar custom_fields JSON por ticket
    # tickets table has custom_fields JSON and raw
    updated=0
    for t in tickets:
        # buscar custom_fields mapeados para este ticket
        # usamos tickets_mapped ya
        import json as j
        # actualizar solo custom_fields
        cf_json=j.dumps(t.get('custom_fields',[]), ensure_ascii=False)
        raw_json=j.dumps(t, ensure_ascii=False)
        cur.execute("UPDATE tickets SET custom_fields=?, raw=? WHERE id=?", (cf_json, raw_json, t['id']))
        updated+=1
        if updated%1000==0:
            print(f"  {updated} tickets DB actualizados")
    con.commit()
    print(f"DB actualizados {updated} tickets")
    con.close()
else:
    print("DB no encontrada, solo JSON mapeado")

print("\nETL completo. Dependencias Entidad->Tributo->Portal->TipoTicket->Tipo Solicitud->Otras conservadas (filtrado se hará en frontend por co-ocurrencia)")
