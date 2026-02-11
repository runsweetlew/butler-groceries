'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getRecipes, getWeekPlan, getRatingStats, getActiveSessions, importRecipe } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { getSuggestions, SuggestedRecipe } from '@/lib/suggested-recipes';

export default function HomePage() {
  const [recipes, setRecipes] = useState<any[]>([]);
  const [weekPlan, setWeekPlan] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [activeSessions, setActiveSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [suggestions, setSuggestions] = useState<SuggestedRecipe[]>([]);
  const [importingUrl, setImportingUrl] = useState<string | null>(null);
  const [importedUrls, setImportedUrls] = useState<Set<string>>(new Set());
  const { t, locale } = useI18n();

  useEffect(() => {
    Promise.all([
      getRecipes({ limit: '5' }).catch(() => []),
      getWeekPlan().catch(() => null),
      getRatingStats().catch(() => null),
      getActiveSessions().catch(() => []),
    ]).then(([r, w, s, a]) => {
      setRecipes(r);
      setWeekPlan(w);
      setStats(s);
      setActiveSessions(a);
      setLoading(false);
    });
  }, []);

  // Refresh suggestions when locale changes
  useEffect(() => {
    setSuggestions(getSuggestions(locale, 4));
  }, [locale]);

  const handleImportSuggestion = async (recipe: SuggestedRecipe) => {
    setImportingUrl(recipe.url);
    try {
      const imported = await importRecipe(recipe.url);
      setImportedUrls(prev => new Set(prev).add(recipe.url));
      // Could navigate to the new recipe, but let's just show success
    } catch (e) {
      alert(locale === 'es' ? 'Error al importar la receta' : 'Failed to import recipe');
    } finally {
      setImportingUrl(null);
    }
  };

  const refreshSuggestions = () => {
    setSuggestions(getSuggestions(locale, 4));
  };

  if (loading) {
    return <div className="text-center py-12 text-gray-400">{t('loading')}</div>;
  }

  const todayStr = new Date().toISOString().split('T')[0];
  const todayPlan = weekPlan?.days?.find((d: any) => d.date === todayStr);
  const availableNights = weekPlan?.days?.filter((d: any) => d.available && !d.meals.length).length || 0;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="card p-6 bg-gradient-to-r from-brand-500 to-brand-600 text-white">
        <h1 className="text-2xl font-bold mb-1">{t('home.welcome')}</h1>
        <p className="text-brand-100">{t('home.subtitle')}</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold text-brand-600">{recipes.length > 4 ? '5+' : recipes.length}</div>
          <div className="text-sm text-gray-500">{t('home.recipes')}</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold text-green-600">{availableNights}</div>
          <div className="text-sm text-gray-500">{t('home.open_nights')}</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold text-purple-600">{stats?.total_ratings || 0}</div>
          <div className="text-sm text-gray-500">{t('home.ratings')}</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold text-red-500">{activeSessions.length}</div>
          <div className="text-sm text-gray-500">{t('home.active_swipes')}</div>
        </div>
      </div>

      {/* 💡 Suggested Recipes */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">
            {locale === 'es' ? '🇪🇨 Recetas Sugeridas' : '💡 Suggested Recipes'}
          </h2>
          <button
            onClick={refreshSuggestions}
            className="text-sm text-brand-500 hover:text-brand-600 flex items-center gap-1"
          >
            🔄 {locale === 'es' ? 'Más' : 'More'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {suggestions.map((recipe) => (
            <div
              key={recipe.url}
              className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 hover:bg-brand-50 transition-colors"
            >
              <div className="text-2xl flex-shrink-0 mt-0.5">{recipe.emoji}</div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{recipe.title}</div>
                <div className="text-xs text-gray-500 mt-0.5">{recipe.description}</div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-xs text-gray-400">{recipe.cuisine}</span>
                  {recipe.time && <span className="text-xs text-gray-400">· {recipe.time}</span>}
                </div>
              </div>
              <div className="flex-shrink-0">
                {importedUrls.has(recipe.url) ? (
                  <span className="text-green-500 text-sm font-medium">✓</span>
                ) : importingUrl === recipe.url ? (
                  <span className="text-xs text-gray-400 animate-pulse">
                    {locale === 'es' ? 'Importando...' : 'Importing...'}
                  </span>
                ) : (
                  <button
                    onClick={() => handleImportSuggestion(recipe)}
                    className="px-2.5 py-1 bg-brand-500 text-white rounded-lg text-xs font-medium hover:bg-brand-600 transition-colors"
                  >
                    + {locale === 'es' ? 'Agregar' : 'Add'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Today's Plan */}
      <div className="card p-5">
        <h2 className="text-lg font-semibold mb-3">{t('home.tonight')}</h2>
        {todayPlan?.meals?.length > 0 ? (
          <div className="space-y-2">
            {todayPlan.meals.map((m: any) => (
              <Link
                key={m.id}
                href={`/recipes/${m.recipe_id}`}
                className="flex items-center gap-3 p-3 rounded-lg bg-brand-50 hover:bg-brand-100 transition-colors"
              >
                <span className="text-2xl">🍽️</span>
                <div>
                  <div className="font-medium">{m.recipe_title}</div>
                  <div className="text-sm text-gray-500">{m.status}</div>
                </div>
                <span className="ml-auto text-brand-500">{t('cook')}</span>
              </Link>
            ))}
          </div>
        ) : todayPlan?.available ? (
          <div className="text-center py-4">
            <p className="text-gray-500 mb-3">{t('home.no_dinner')}</p>
            <div className="flex gap-3 justify-center">
              <Link href="/planner" className="btn-primary">{t('home.plan_something')}</Link>
              <Link href="/swipe" className="btn-secondary">🔥 {t('nav.swipe')}</Link>
            </div>
          </div>
        ) : (
          <div className="text-center py-4 text-gray-500">
            <p>{t('home.out_tonight')}</p>
          </div>
        )}
      </div>

      {/* Week Overview */}
      {weekPlan && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">{t('home.this_week')}</h2>
            <Link href="/planner" className="text-sm text-brand-500 hover:text-brand-600">{t('home.view_full_plan')}</Link>
          </div>
          <div className="grid grid-cols-7 gap-2">
            {weekPlan.days?.map((day: any) => (
              <div
                key={day.date}
                className={`text-center p-2 rounded-lg text-sm ${
                  day.date === todayStr
                    ? 'bg-brand-500 text-white'
                    : day.available
                    ? day.meals.length ? 'bg-green-50 text-green-700' : 'bg-gray-50'
                    : 'bg-red-50 text-red-400'
                }`}
              >
                <div className="font-medium">{t(`day.${day.day_name.slice(0, 3)}`, day.day_name.slice(0, 3))}</div>
                <div className="text-xs mt-1">
                  {day.meals.length > 0 ? '✅' : day.available ? '—' : '🚫'}
                </div>
              </div>
            ))}
          </div>

          {/* Rule status */}
          {weekPlan.rule_status?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">{t('home.rule_status')}</div>
              <div className="flex flex-wrap gap-2">
                {weekPlan.rule_status.map((r: any) => (
                  <span
                    key={r.rule_id}
                    className={`badge ${
                      r.status === 'ok' ? 'bg-green-100 text-green-700'
                      : r.status === 'warning' ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {r.status === 'ok' ? '✓' : r.status === 'warning' ? '⚠' : '✗'} {r.message}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Link href="/recipes/import" className="card p-4 text-center hover:shadow-md transition-shadow">
          <div className="text-2xl mb-1">📥</div>
          <div className="text-sm font-medium">{t('home.import_recipe')}</div>
        </Link>
        <Link href="/swipe" className="card p-4 text-center hover:shadow-md transition-shadow">
          <div className="text-2xl mb-1">🔥</div>
          <div className="text-sm font-medium">{t('home.swipe_together')}</div>
        </Link>
        <Link href="/planner" className="card p-4 text-center hover:shadow-md transition-shadow">
          <div className="text-2xl mb-1">📅</div>
          <div className="text-sm font-medium">{t('home.plan_week')}</div>
        </Link>
        <Link href="/shopping" className="card p-4 text-center hover:shadow-md transition-shadow">
          <div className="text-2xl mb-1">🛒</div>
          <div className="text-sm font-medium">{t('home.shopping_list')}</div>
        </Link>
      </div>

      {/* Recent Recipes */}
      {recipes.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">{t('home.recent_recipes')}</h2>
            <Link href="/recipes" className="text-sm text-brand-500 hover:text-brand-600">{t('home.view_all')}</Link>
          </div>
          <div className="space-y-2">
            {recipes.map((r) => (
              <Link
                key={r.id}
                href={`/recipes/${r.id}`}
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="w-12 h-12 rounded-lg bg-brand-100 flex items-center justify-center text-xl flex-shrink-0">
                  {r.image_url ? (
                    <img src={r.image_path || r.image_url} alt="" className="w-full h-full object-cover rounded-lg" />
                  ) : '🍽️'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{r.title}</div>
                  <div className="text-xs text-gray-500">
                    {r.cuisine && <span>{r.cuisine}</span>}
                    {r.total_time_min && <span> · {r.total_time_min} {t('min')}</span>}
                    {r.avg_rating && <span> · {'⭐'.repeat(Math.round(r.avg_rating))}</span>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
