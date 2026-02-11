'use client';

import { useState, useEffect, useContext } from 'react';
import { getWeekPlan, getRecipes, addToPlan, deletePlan, updatePlan, suggestMeals, addCalendarEvent, deleteCalendarEvent } from '@/lib/api';
import { UserContext } from '@/lib/user-context';
import Link from 'next/link';
import { format, addDays, subDays, startOfWeek } from 'date-fns';

export default function PlannerPage() {
  const { currentUser } = useContext(UserContext);
  const [weekPlan, setWeekPlan] = useState<any>(null);
  const [weekStart, setWeekStart] = useState(() => {
    const today = new Date();
    return startOfWeek(today, { weekStartsOn: 1 }); // Monday
  });
  const [recipes, setRecipes] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState<string | null>(null); // date string or null
  const [selectedRecipe, setSelectedRecipe] = useState<number | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [showBlockDay, setShowBlockDay] = useState<string | null>(null);
  const [blockReason, setBlockReason] = useState('');
  const [loading, setLoading] = useState(true);

  const loadWeek = async () => {
    setLoading(true);
    const dateStr = format(weekStart, 'yyyy-MM-dd');
    const data = await getWeekPlan(dateStr).catch(() => null);
    setWeekPlan(data);
    setLoading(false);
  };

  useEffect(() => { loadWeek(); }, [weekStart]);
  useEffect(() => { getRecipes({ limit: '200' }).then(setRecipes).catch(() => {}); }, []);

  const handleAddMeal = async (dateStr: string) => {
    if (!selectedRecipe) return;
    await addToPlan({ date: dateStr, recipe_id: selectedRecipe, meal_type: 'dinner' });
    setShowAdd(null);
    setSelectedRecipe(null);
    await loadWeek();
  };

  const handleRemoveMeal = async (planId: number) => {
    if (!confirm('Remove this meal from the plan?')) return;
    await deletePlan(planId);
    await loadWeek();
  };

  const handleMarkCooked = async (planId: number) => {
    await updatePlan(planId, { status: 'cooked' });
    await loadWeek();
  };

  const handleSuggest = async () => {
    if (!weekPlan) return;
    setSuggesting(true);
    try {
      const available = weekPlan.days
        .filter((d: any) => d.available && d.meals.length === 0)
        .map((d: any) => d.date);

      if (available.length === 0) {
        alert('No available nights to fill!');
        return;
      }

      const result = await suggestMeals({
        week_start: format(weekStart, 'yyyy-MM-dd'),
        available_dates: available,
        context: 'dinner',
      });

      if (result.suggestions?.length > 0) {
        for (const s of result.suggestions) {
          await addToPlan({ date: s.date, recipe_id: s.recipe_id, meal_type: 'dinner', notes: s.reason || '' });
        }
        await loadWeek();
      }
    } finally {
      setSuggesting(false);
    }
  };

  const handleBlockDay = async (dateStr: string) => {
    await addCalendarEvent({
      date: dateStr,
      summary: blockReason || 'Busy',
      is_dinner_conflict: true,
    });
    setShowBlockDay(null);
    setBlockReason('');
    await loadWeek();
  };

  const handleUnblockDay = async (eventId: number) => {
    await deleteCalendarEvent(eventId);
    await loadWeek();
  };

  if (loading) return <div className="text-center py-12 text-gray-400">Loading planner...</div>;

  return (
    <div className="space-y-4">
      {/* Week Navigation */}
      <div className="flex items-center justify-between">
        <button onClick={() => setWeekStart(subDays(weekStart, 7))} className="btn-secondary">← Prev</button>
        <h1 className="text-xl font-bold">
          📅 {format(weekStart, 'MMM d')} — {format(addDays(weekStart, 6), 'MMM d, yyyy')}
        </h1>
        <button onClick={() => setWeekStart(addDays(weekStart, 7))} className="btn-secondary">Next →</button>
      </div>

      {/* AI Suggest Button */}
      <div className="flex gap-3">
        <button
          onClick={handleSuggest}
          disabled={suggesting}
          className="btn-primary flex-1"
        >
          {suggesting ? '🤔 Thinking...' : '🧠 AI Suggest Meals for Open Nights'}
        </button>
      </div>

      {/* Rule Status */}
      {weekPlan?.rule_status?.length > 0 && (
        <div className="card p-3">
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

      {/* Day Cards */}
      <div className="space-y-3">
        {weekPlan?.days?.map((day: any) => {
          const isToday = day.date === format(new Date(), 'yyyy-MM-dd');
          const isPast = new Date(day.date) < new Date(format(new Date(), 'yyyy-MM-dd'));

          return (
            <div
              key={day.date}
              className={`card p-4 ${isToday ? 'ring-2 ring-brand-500' : ''} ${isPast ? 'opacity-60' : ''}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-lg">{day.day_name}</span>
                  <span className="text-sm text-gray-400">{day.date}</span>
                  {isToday && <span className="badge bg-brand-100 text-brand-700">Today</span>}
                </div>
                <div className="flex items-center gap-2">
                  {day.available ? (
                    <span className="badge bg-green-100 text-green-700">Available</span>
                  ) : (
                    <span className="badge bg-red-100 text-red-700">Busy</span>
                  )}
                </div>
              </div>

              {/* Calendar events */}
              {day.calendar_events?.length > 0 && (
                <div className="mb-2 space-y-1">
                  {day.calendar_events.map((e: any, idx: number) => (
                    <div key={e.id || `ha-${idx}`} className={`flex items-center gap-2 text-sm ${e.is_dinner_conflict ? 'text-red-500' : 'text-gray-500'}`}>
                      <span>{e.source === 'homeassistant' ? '📅' : '🚫'}</span>
                      <span className="flex-1">
                        {e.start_time && <span className="text-xs text-gray-400 mr-1">{e.start_time}</span>}
                        {e.summary}
                        {e.location && <span className="text-xs text-gray-400 ml-1">📍 {e.location}</span>}
                        {e.calendar && <span className="text-xs text-gray-400 ml-1">({e.calendar})</span>}
                      </span>
                      {e.is_dinner_conflict && <span className="text-xs badge bg-red-100 text-red-600">dinner conflict</span>}
                      {e.id && e.source !== 'homeassistant' && (
                        <button onClick={() => handleUnblockDay(e.id)} className="text-xs text-gray-400 hover:text-red-500">✕</button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Planned meals */}
              {day.meals?.length > 0 ? (
                <div className="space-y-2">
                  {day.meals.map((m: any) => (
                    <div key={m.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                      <span className="text-xl">{m.status === 'cooked' ? '✅' : '🍽'}</span>
                      <Link href={`/recipes/${m.recipe_id}`} className="flex-1 font-medium hover:text-brand-600">
                        {m.recipe_title}
                      </Link>
                      <div className="flex gap-1">
                        {m.status !== 'cooked' && (
                          <>
                            <Link href={`/cook/${m.recipe_id}`} className="text-sm text-brand-500 hover:underline">
                              Cook
                            </Link>
                            <button onClick={() => handleMarkCooked(m.id)} className="text-sm text-green-500 hover:underline ml-2">
                              ✓ Done
                            </button>
                          </>
                        )}
                        <button onClick={() => handleRemoveMeal(m.id)} className="text-sm text-red-400 hover:text-red-600 ml-2">
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : day.available ? (
                <div className="flex gap-2">
                  {showAdd === day.date ? (
                    <div className="flex gap-2 flex-1">
                      <select
                        className="input flex-1"
                        value={selectedRecipe || ''}
                        onChange={(e) => setSelectedRecipe(Number(e.target.value))}
                      >
                        <option value="">Pick a recipe...</option>
                        {recipes.map(r => (
                          <option key={r.id} value={r.id}>{r.title}</option>
                        ))}
                      </select>
                      <button onClick={() => handleAddMeal(day.date)} disabled={!selectedRecipe} className="btn-primary text-sm">
                        Add
                      </button>
                      <button onClick={() => setShowAdd(null)} className="btn-secondary text-sm">✕</button>
                    </div>
                  ) : (
                    <>
                      <button onClick={() => setShowAdd(day.date)} className="text-sm text-brand-500 hover:underline">
                        + Add meal
                      </button>
                      <button onClick={() => setShowBlockDay(day.date)} className="text-sm text-gray-400 hover:text-red-500 ml-2">
                        Block night
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic">Not cooking tonight</p>
              )}

              {/* Block day dialog */}
              {showBlockDay === day.date && (
                <div className="mt-2 flex gap-2">
                  <input
                    className="input flex-1"
                    placeholder="Reason (e.g., Restaurant, Travel)"
                    value={blockReason}
                    onChange={(e) => setBlockReason(e.target.value)}
                  />
                  <button onClick={() => handleBlockDay(day.date)} className="btn-danger text-sm">Block</button>
                  <button onClick={() => setShowBlockDay(null)} className="btn-secondary text-sm">✕</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
