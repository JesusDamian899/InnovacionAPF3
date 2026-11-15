"""Anexo E - Estimación del impacto en stock de seguridad (Tiendas 3A, APF3).
Compara el stock de seguridad necesario para un nivel de servicio del 95 %
cuando el pedido se basa en la regla actual (repetir la venta de hace 7 días)
frente al pronóstico del modelo exportado. Usa solo el conjunto de prueba
(22/10 al 08/11/2026) y el modelo ya seleccionado: no reentrena ni elige nada."""
import os, numpy as np, pandas as pd, joblib, json, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(BASE_DIR, 'data', 'dataset_ventas_3a.csv')
if not os.path.exists(DEFAULT_CSV):
    DEFAULT_CSV = os.path.join(BASE_DIR, 'dataset_ventas_3a.csv')
DEFAULT_MODEL = os.path.join(BASE_DIR, 'modelo_demanda_3a.joblib')

CSV = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
MODEL = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL

LEAD = {'fv':1,'lac':2,'aba':3,'beb':2,'lim':4,'cui':5,'pan':1}   # días, tabla categorias (Supabase)
Z95 = 1.645
df = pd.read_csv(CSV); df['fecha'] = pd.to_datetime(df['fecha'])
df = df.sort_values(['producto_id','fecha']).reset_index(drop=True)
g = df.groupby('producto_id')['unidades_vendidas']
df['lag_1d'] = g.shift(1); df['lag_7d'] = g.shift(7)
df['media_movil_7d'] = g.transform(lambda x: x.shift(1).rolling(7).mean())
df['std_movil_7d'] = g.transform(lambda x: x.shift(1).rolling(7).std().fillna(0))
te = df.dropna()[lambda d: d['fecha'] >= '2026-10-22'].copy()
feats = ['precio','costo','lag_1d','lag_7d','media_movil_7d','std_movil_7d','dia_semana','es_fin_de_semana','es_quincena','categoria_id']
te['pred_modelo'] = joblib.load(MODEL).predict(te[feats])
te['err_regla'] = te['unidades_vendidas'] - te['lag_7d']
te['err_modelo'] = te['unidades_vendidas'] - te['pred_modelo']
rows = []
for pid, d in te.groupby('producto_id'):
    L = LEAD[d['categoria_id'].iloc[0]]; c = d['costo'].iloc[0]
    ss_r = Z95 * d['err_regla'].std() * np.sqrt(L); ss_m = Z95 * d['err_modelo'].std() * np.sqrt(L)
    rows.append(dict(producto_id=pid, categoria=d['categoria_nombre'].iloc[0], unidad=d['unidad'].iloc[0], lead=L, costo=c,
                     ss_regla=ss_r, ss_modelo=ss_m, soles_regla=ss_r*c, soles_modelo=ss_m*c))
r = pd.DataFrame(rows)
res = {
  'ss_regla_soles': round(r['soles_regla'].sum(),2), 'ss_modelo_soles': round(r['soles_modelo'].sum(),2),
  'ahorro_soles': round(r['soles_regla'].sum()-r['soles_modelo'].sum(),2),
  'ahorro_pct': round((1-r['soles_modelo'].sum()/r['soles_regla'].sum())*100,1),
  'skus_con_menor_ss': int((r['ss_modelo']<r['ss_regla']).sum()),
  'error_abs_diario_regla_unid': round(te.groupby('fecha')['err_regla'].apply(lambda s: s.abs().sum()).mean(),1),
  'error_abs_diario_modelo_unid': round(te.groupby('fecha')['err_modelo'].apply(lambda s: s.abs().sum()).mean(),1),
  'subestimaciones_graves_regla': int((te['err_regla']>10).sum()), 'subestimaciones_graves_modelo': int((te['err_modelo']>10).sum()),
  'por_categoria': r.groupby('categoria')[['soles_regla','soles_modelo']].sum().round(2).to_dict('index')
}
print(json.dumps(res, indent=1, ensure_ascii=False))
