"""Anexo E - Comparación del motor estadístico del MVP (APF2, forecast.ts) con el modelo APF3.
Traducción a Python de fitDemandModel/predictForDate (src/engine/forecast.ts):
índice semanal con shrinkage 0,75, tendencia lineal sobre la serie desestacionalizada
(acotada a ±35 % semanal) y mezcla 65/35 con un nivel EWMA (alfa 0,25, últimos 14 días).
Ventana de historia: 56 días (valor por defecto del MVP). Pronóstico a 1 día para cada fecha
del conjunto de prueba, reentrenando solo con días anteriores (sin fuga)."""
import os, sys, json, numpy as np, pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(BASE_DIR, 'data', 'dataset_ventas_3a.csv')
if not os.path.exists(DEFAULT_CSV):
    DEFAULT_CSV = os.path.join(BASE_DIR, 'dataset_ventas_3a.csv')
CSV = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

df = pd.read_csv(CSV, parse_dates=['fecha']).sort_values(['producto_id','fecha'])
def fit_predict(hist, fecha_obj):
    y = hist['unidades_vendidas'].to_numpy(float); wd = hist['fecha'].dt.weekday.to_numpy()
    overall = y.mean() or 1
    raw = np.array([y[wd==k].mean()/overall if (wd==k).any() else 1 for k in range(7)])
    shr = 0.75*raw + 0.25; idx = shr/shr.mean()
    des = y/idx[wd]; xs = np.arange(len(y)); mx, my = xs.mean(), des.mean()
    slope = ((xs-mx)*(des-my)).sum()/((xs-mx)**2).sum()
    maxs = 0.35*max(my,0.01)/7; slope = float(np.clip(slope,-maxs,maxs)); intercept = my - slope*mx
    lvl = None
    for v in des[-14:]: lvl = v if lvl is None else 0.25*v + 0.75*lvl
    t = (fecha_obj - hist['fecha'].iloc[0]).days
    base = 0.65*(intercept+slope*t) + 0.35*(lvl + slope*(t-(len(y)-1)))
    return max(0.0, base*idx[fecha_obj.weekday()])
rows = []
for pid, d in df.groupby('producto_id'):
    d = d.reset_index(drop=True)
    for i in range(len(d)):
        f = d.loc[i,'fecha']
        if f < pd.Timestamp('2026-10-22'): continue
        hist = d[(d['fecha']<f)].tail(56)
        rows.append((pid, f, d.loc[i,'unidades_vendidas'], fit_predict(hist, f)))
r = pd.DataFrame(rows, columns=['producto_id','fecha','real','pred'])
e = r['real']-r['pred']
out = dict(n=len(r), RMSE=round(float(np.sqrt((e**2).mean())),2), MAE=round(float(e.abs().mean()),2),
           R2=round(float(1-(e**2).sum()/((r['real']-r['real'].mean())**2).sum()),3),
           MAPE=round(float((e.abs()/r['real']).mean()*100),2))
print(json.dumps(out))
