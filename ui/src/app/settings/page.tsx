'use client';

import { useState, useEffect, useContext } from 'react';
import { getRules, createRule, updateRule, deleteRule, getPantryStaples, getTasteProfile, compareTastes, getTasteInsights, parseNaturalRule } from '@/lib/api';
import { UserContext } from '@/lib/user-context';

export default function SettingsPage() {
  const { currentUser, users } = useContext(UserContext);
  const [tab, setTab] = useState<'rules' | 'pantry' | 'taste'>('rules');

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">⚙️ Settings</h1>

      <div className="flex gap-2">
        {(['rules', 'pantry', 'taste'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg font-medium capitalize ${
              tab === t ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {t === 'rules' ? '📏 Rules' : t === 'pantry' ? '🥫 Pantry' : '🧠 Taste'}
          </button>
        ))}
      </div>

      {tab === 'rules' && <RulesTab />}
      {tab === 'pantry' && <PantryTab />}
      {tab === 'taste' && <TasteTab currentUser={currentUser} users={users} />}
    </div>
  );
}

// ---------- Rules ----------
function RulesTab() {
  const [rules, setRules] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [ruleText, setRuleText] = useState('');
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const [parseError, setParseError] = useState('');

  useEffect(() => { getRules().then(setRules).catch(() => {}); }, []);

  const ruleDescriptions: Record<string, string> = {
    protein_max_per_week: 'Limits how often a protein appears',
    protein_min_per_period: 'Requires a protein at least X times',
    no_repeat_within_days: 'Prevents repeating the same recipe',
    min_tag_per_week: 'Requires at least X meals with a tag',
    max_tag_per_week: 'Limits meals with a specific tag',
  };

  const ruleIcons: Record<string, string> = {
    protein_max_per_week: '🔻',
    protein_min_per_period: '🔺',
    no_repeat_within_days: '🔄',
    min_tag_per_week: '📈',
    max_tag_per_week: '📉',
  };

  const formatConfig = (rule: any) => {
    const c = rule.config;
    const t = rule.rule_type;
    if (t === 'protein_max_per_week')
      return `Max ${c.max}× ${c.protein} per ${c.period_days === 7 ? 'week' : c.period_days + ' days'}`;
    if (t === 'protein_min_per_period')
      return `At least ${c.min}× ${c.protein} per ${c.period_days === 7 ? 'week' : c.period_days === 14 ? '2 weeks' : c.period_days + ' days'}`;
    if (t === 'no_repeat_within_days')
      return `No repeats within ${c.min_days_between_repeat} days`;
    if (t === 'min_tag_per_week')
      return `At least ${c.min}× "${c.tag}" per ${c.period_days === 7 ? 'week' : c.period_days + ' days'}`;
    if (t === 'max_tag_per_week')
      return `Max ${c.max}× "${c.tag}" per ${c.period_days === 7 ? 'week' : c.period_days + ' days'}`;
    return JSON.stringify(c);
  };

  const handleParse = async () => {
    if (!ruleText.trim()) return;
    setParsing(true);
    setParseError('');
    setPreview(null);
    try {
      const result = await parseNaturalRule(ruleText);
      if (result.success) {
        setPreview(result);
      } else {
        setParseError(result.error || 'Could not understand that rule. Try rephrasing.');
      }
    } catch (e: any) {
      setParseError(e.message || 'Failed to parse rule');
    } finally {
      setParsing(false);
    }
  };

  const handleSavePreview = async () => {
    if (!preview) return;
    await createRule({
      name: preview.name,
      rule_type: preview.rule_type,
      config: preview.config,
      active: true,
    });
    const updated = await getRules();
    setRules(updated);
    setShowAdd(false);
    setRuleText('');
    setPreview(null);
    setParseError('');
  };

  const handleToggle = async (rule: any) => {
    await updateRule(rule.id, { active: !rule.active });
    const updated = await getRules();
    setRules(updated);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this rule?')) return;
    await deleteRule(id);
    setRules(rules.filter(r => r.id !== id));
  };

  const examples = [
    'No more than 2 chicken dishes per week',
    'We should eat fish at least once every two weeks',
    'Don\'t repeat the same meal within 10 days',
    'At least 3 vegetarian meals per week',
    'Max 1 pasta dish per week',
    'Eat salmon at least once a week',
  ];

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">Rules the meal planner must follow.</p>
        <button
          onClick={() => { setShowAdd(!showAdd); setPreview(null); setParseError(''); setRuleText(''); }}
          className="btn-primary text-sm"
        >
          {showAdd ? '✕ Cancel' : '+ Add Rule'}
        </button>
      </div>

      {showAdd && (
        <div className="card p-5 space-y-4 border-2 border-brand-200">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Describe your rule in plain English
            </label>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="e.g. No more than 2 chicken dishes per week"
                value={ruleText}
                onChange={e => { setRuleText(e.target.value); setPreview(null); setParseError(''); }}
                onKeyDown={e => e.key === 'Enter' && !parsing && handleParse()}
                autoFocus
              />
              <button
                onClick={handleParse}
                disabled={parsing || !ruleText.trim()}
                className="btn-primary text-sm whitespace-nowrap disabled:opacity-50"
              >
                {parsing ? (
                  <span className="flex items-center gap-1">
                    <span className="animate-spin">🤔</span> Parsing...
                  </span>
                ) : '✨ Parse'}
              </button>
            </div>
          </div>

          {/* Examples */}
          {!preview && !parseError && (
            <div>
              <p className="text-xs text-gray-400 mb-2">Try something like:</p>
              <div className="flex flex-wrap gap-1.5">
                {examples.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => { setRuleText(ex); setPreview(null); setParseError(''); }}
                    className="text-xs px-2.5 py-1 bg-gray-100 hover:bg-brand-50 hover:text-brand-600 rounded-full text-gray-500 transition-colors"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Parse Error */}
          {parseError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              ⚠️ {parseError}
            </div>
          )}

          {/* Preview */}
          {preview && (
            <div className="p-4 bg-brand-50 border border-brand-200 rounded-lg space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-semibold text-brand-800">
                    {ruleIcons[preview.rule_type] || '📏'} {preview.name}
                  </div>
                  <div className="text-sm text-brand-600 mt-1">{preview.explanation}</div>
                </div>
                <span className="text-xs bg-brand-200 text-brand-700 px-2 py-0.5 rounded-full">
                  {ruleDescriptions[preview.rule_type] || preview.rule_type}
                </span>
              </div>

              <div className="text-xs bg-white/60 rounded p-2 font-mono text-gray-600">
                {formatConfig({ rule_type: preview.rule_type, config: preview.config })}
              </div>

              <div className="flex gap-2 pt-1">
                <button onClick={handleSavePreview} className="btn-primary text-sm">
                  ✅ Add This Rule
                </button>
                <button
                  onClick={() => { setPreview(null); }}
                  className="btn-secondary text-sm"
                >
                  Try Again
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Existing Rules */}
      {rules.map(rule => (
        <div key={rule.id} className={`card p-4 transition-opacity ${!rule.active ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">
                {ruleIcons[rule.rule_type] || '📏'} {rule.name}
              </div>
              <div className="text-sm text-gray-500 mt-0.5">{formatConfig(rule)}</div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleToggle(rule)}
                className={`text-sm font-medium transition-colors ${
                  rule.active
                    ? 'text-green-600 hover:text-yellow-600'
                    : 'text-gray-400 hover:text-green-600'
                }`}
              >
                {rule.active ? '✅ Active' : '⏸ Paused'}
              </button>
              <button onClick={() => handleDelete(rule.id)} className="text-gray-300 hover:text-red-500 transition-colors">
                🗑
              </button>
            </div>
          </div>
        </div>
      ))}

      {rules.length === 0 && !showAdd && (
        <div className="card p-8 text-center text-gray-400">
          <p className="text-lg mb-2">No rules yet</p>
          <p className="text-sm">Add a rule like &ldquo;No more than 2 chicken dishes per week&rdquo;</p>
        </div>
      )}
    </div>
  );
}

// ---------- Pantry ----------
function PantryTab() {
  const [staples, setStaples] = useState<any[]>([]);
  const [newName, setNewName] = useState('');

  useEffect(() => { getPantryStaples().then(setStaples).catch(() => {}); }, []);

  const handleAdd = async () => {
    if (!newName.trim()) return;
    const resp = await fetch(`/api/shopping/pantry/staples?name=${encodeURIComponent(newName)}`, { method: 'POST' });
    const item = await resp.json();
    setStaples([...staples, item]);
    setNewName('');
  };

  const handleRemove = async (id: number) => {
    await fetch(`/api/shopping/pantry/staples/${id}`, { method: 'DELETE' });
    setStaples(staples.filter(s => s.id !== id));
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">Items you always have — excluded from shopping lists.</p>

      <div className="flex gap-2">
        <input className="input flex-1" placeholder="Add a pantry staple..." value={newName} onChange={e => setNewName(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleAdd()} />
        <button onClick={handleAdd} className="btn-primary">Add</button>
      </div>

      <div className="card divide-y divide-gray-50">
        {staples.map(s => (
          <div key={s.id} className="flex items-center justify-between px-4 py-2">
            <span>{s.name}</span>
            <button onClick={() => handleRemove(s.id)} className="text-red-400 hover:text-red-600 text-sm">✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Taste Profile ----------
function TasteTab({ currentUser, users }: { currentUser: any; users: any[] }) {
  const [profile, setProfile] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [insights, setInsights] = useState<any>(null);
  const [loadingInsights, setLoadingInsights] = useState(false);

  useEffect(() => {
    if (currentUser) {
      getTasteProfile(currentUser.id).then(setProfile).catch(() => {});
    }
    compareTastes().then(setComparison).catch(() => {});
  }, [currentUser]);

  const handleGetInsights = async () => {
    if (!currentUser) return;
    setLoadingInsights(true);
    try {
      const data = await getTasteInsights(currentUser.id);
      setInsights(data.insights);
    } finally {
      setLoadingInsights(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">Your taste profile, built from ratings and cooking history.</p>

      {profile?.preferences && Object.keys(profile.preferences).length > 0 ? (
        <div className="card p-5">
          <h3 className="font-semibold mb-3">{currentUser?.name}&apos;s Taste Profile</h3>
          {Object.entries(profile.preferences).map(([dimension, values]: [string, any]) => (
            <div key={dimension} className="mb-4">
              <h4 className="text-sm font-medium text-gray-600 uppercase tracking-wide mb-2">{dimension}</h4>
              <div className="space-y-1">
                {Object.entries(values)
                  .sort(([,a]: any, [,b]: any) => b - a)
                  .map(([value, score]: [string, any]) => (
                    <div key={value} className="flex items-center gap-2">
                      <span className="text-sm w-24 truncate">{value}</span>
                      <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full"
                          style={{ width: `${Math.round(score * 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-10 text-right">{Math.round(score * 100)}%</span>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-6 text-center text-gray-500">
          <p>No taste data yet. Rate some recipes to build your profile!</p>
        </div>
      )}

      {/* AI Insights */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">🧠 AI Insights</h3>
          <button onClick={handleGetInsights} disabled={loadingInsights} className="btn-primary text-sm">
            {loadingInsights ? '🤔 Thinking...' : 'Generate Insights'}
          </button>
        </div>
        {insights && (
          <div className="space-y-2">
            {insights.map((insight: any, i: number) => (
              <div key={i} className="p-3 bg-brand-50 rounded-lg text-sm">
                {typeof insight === 'string' ? insight : insight.message}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Comparison */}
      {comparison?.agreements?.length > 0 && (
        <div className="card p-5">
          <h3 className="font-semibold mb-3">👫 You & Your Partner</h3>

          {comparison.agreements.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-green-600 mb-2">💚 You both love</h4>
              <div className="flex flex-wrap gap-2">
                {comparison.agreements.map((a: any, i: number) => (
                  <span key={i} className="badge bg-green-100 text-green-700">{a.value}</span>
                ))}
              </div>
            </div>
          )}

          {comparison.disagreements?.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-red-600 mb-2">🤷 You disagree on</h4>
              <div className="flex flex-wrap gap-2">
                {comparison.disagreements.map((d: any, i: number) => (
                  <span key={i} className="badge bg-red-100 text-red-700">{d.value}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
