import { createContext, type Dispatch, type ReactNode, useContext, useEffect, useMemo, useReducer, useState } from 'react';
import { Loader2, RefreshCw, AlertTriangle } from 'lucide-react';
import { CATEGORIES } from '@/data/catalog';
import type { Category, Product } from '@/domain/types';
import { type Alert, buildAlerts } from '@/engine/alerts';
import { computeInsight, type ProductInsight } from '@/engine/inventory';
import { fetchAllBackendData } from '@/services/apiClient';
import { type Action, reducer } from './reducer';
import { type AppState, createInitialState } from './state';

export interface StoreValue {
  state: AppState;
  dispatch: Dispatch<Action>;
  /** Predicciones por producto, recalculadas ante cualquier cambio del estado. */
  insights: Record<string, ProductInsight>;
  alerts: Alert[];
  categories: Category[];
  categoryById: Record<string, Category>;
  productById: Record<string, Product>;
}

const StoreContext = createContext<StoreValue | null>(null);

/** Minutos de reloj virtual por segundo real a velocidad 1×. */
export const SIM_MINUTES_PER_SECOND = 5;

export function StoreProvider({ children, initialState }: { children: ReactNode; initialState?: AppState }) {
  const [state, dispatch] = useReducer(reducer, initialState, (init) => init ?? createInitialState());
  const [loading, setLoading] = useState(!initialState);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  // Carga e hidratación estricta desde el Backend y Base de Datos Supabase (Punto 2)
  useEffect(() => {
    if (initialState) return;
    let mounted = true;

    async function bootstrap() {
      setLoading(true);
      setLoadError(null);
      try {
        const data = await fetchAllBackendData();
        if (!mounted) return;
        if (data && data.products.length > 0) {
          dispatch({
            type: 'HYDRATE_FROM_BACKEND',
            products: data.products,
            movements: data.movements,
            history: data.history,
            todaySales: data.todaySales,
          });
          setLoading(false);
        } else {
          setLoadError('El servidor backend respondió pero no se encontraron productos en la base de datos de Supabase.');
        }
      } catch (err: any) {
        if (!mounted) return;
        setLoadError(err?.message || 'No se pudo conectar con el backend en Render / Supabase.');
      }
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [retryCount, initialState]);

  const { running, speed } = state.simulator;

  // Simulador: avanza el reloj virtual y genera ventas mientras está activo.
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => dispatch({ type: 'TICK', minutes: SIM_MINUTES_PER_SECOND * speed }), 1000);
    return () => window.clearInterval(id);
  }, [running, speed]);

  const { products, history, todaySales, orders, now, settings, snoozed } = state;

  const insights = useMemo(() => {
    const pendingBy = new Map<string, typeof orders>();
    for (const o of orders) {
      if (o.status !== 'pendiente') continue;
      pendingBy.set(o.productId, [...(pendingBy.get(o.productId) ?? []), o]);
    }
    const out: Record<string, ProductInsight> = {};
    for (const p of products) {
      out[p.id] = computeInsight({
        product: p,
        history: history[p.id] ?? [],
        soldToday: todaySales[p.id] ?? 0,
        pendingOrders: pendingBy.get(p.id) ?? [],
        now,
        settings,
      });
    }
    return out;
  }, [products, history, todaySales, orders, now, settings]);

  const alerts = useMemo(() => buildAlerts(products, insights, orders, now, snoozed), [products, insights, orders, now, snoozed]);

  const lookups = useMemo(
    () => ({
      categories: CATEGORIES,
      categoryById: Object.fromEntries(CATEGORIES.map((c) => [c.id, c])),
    }),
    [],
  );
  const productById = useMemo(() => Object.fromEntries(products.map((p) => [p.id, p])), [products]);

  const value = useMemo<StoreValue>(
    () => ({ state, dispatch, insights, alerts, productById, ...lookups }),
    [state, insights, alerts, productById, lookups],
  );

  // Pantalla de espera / conexión obligatoria al Backend en Render y Supabase (Cero Mocks)
  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#0B1528] px-4 text-white">
        <div className="relative flex w-full max-w-md flex-col items-center text-center">
          {/* Logo Tiendas 3A */}
          <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-[#D6001C] to-[#E53935] shadow-xl shadow-red-600/30">
            <span className="text-2xl font-black tracking-tighter text-white">3A</span>
          </div>

          <h1 className="text-xl font-bold tracking-tight text-white mb-1.5">
            Sistema de Inventario Inteligente
          </h1>
          <p className="text-xs text-slate-400 mb-6">
            Tiendas 3A — Sede Av. Tantamayo 1032, SMP · Modelo Predictivo APF3
          </p>

          <div className="w-full rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-2xl backdrop-blur-md mb-4 text-left">
            <div className="flex items-start gap-3">
              <Loader2 className="mt-0.5 h-5 w-5 animate-spin text-[#D6001C] shrink-0" />
              <div>
                <p className="text-xs font-semibold text-slate-200">
                  Conectando con Backend y Supabase...
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                  Cargando catálogo oficial de 33 productos, registros de kardex e historial de ventas desde la nube.
                </p>
                <p className="mt-2 text-[10px] text-slate-500 italic">
                  * Si el backend gratuito en Render está en reposo (cold start), puede tardar entre 20 y 35 segundos en responder.
                </p>
              </div>
            </div>
          </div>

          {loadError && (
            <div className="w-full rounded-2xl border border-rose-500/30 bg-rose-950/40 p-4 text-left mb-4">
              <div className="flex items-center gap-2 text-rose-300 text-xs font-bold mb-1">
                <AlertTriangle size={15} />
                <span>Error de conexión con el Backend</span>
              </div>
              <p className="text-[11px] text-rose-200/80 leading-relaxed mb-3">
                {loadError}
              </p>
              <button
                type="button"
                onClick={() => setRetryCount((c) => c + 1)}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#D6001C] py-2.5 text-xs font-bold text-white shadow-md shadow-red-600/20 hover:bg-[#b00017] transition-all"
              >
                <RefreshCw size={13} />
                Reintentar conexión
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreValue {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStore debe usarse dentro de <StoreProvider>');
  return ctx;
}
