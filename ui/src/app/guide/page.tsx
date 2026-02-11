'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';

const STEPS = [
  {
    title: "Welcome to Butler Groceries! 🍳",
    icon: "👋",
    content: (
      <div className="space-y-3">
        <p>Butler Groceries is your personal recipe & meal planning assistant — built just for the two of you.</p>
        <p>Here&apos;s what you can do:</p>
        <ul className="space-y-2 ml-4">
          <li>📥 <strong>Import recipes</strong> from any website</li>
          <li>🔥 <strong>Swipe together</strong> to pick meals (like Tinder!)</li>
          <li>📅 <strong>Plan your week</strong> with smart suggestions</li>
          <li>👨‍🍳 <strong>Cook step-by-step</strong> with built-in timers</li>
          <li>⭐ <strong>Rate together</strong> — both of you rate every meal</li>
          <li>🧠 <strong>AI learns your taste</strong> and gets better over time</li>
          <li>🛒 <strong>Auto shopping lists</strong> from your plan</li>
        </ul>
      </div>
    ),
  },
  {
    title: "Step 1: Import Your Recipes 📥",
    icon: "📥",
    content: (
      <div className="space-y-3">
        <p>Start by building your recipe collection. You can import recipes from almost any website!</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">How to import:</p>
          <ol className="space-y-2 ml-4 list-decimal">
            <li>Go to the <strong>Import</strong> page</li>
            <li>Paste a recipe URL (from NYT Cooking, Bon Appétit, food blogs, etc.)</li>
            <li>Click <strong>Import</strong> — AI extracts everything automatically</li>
            <li>Review the recipe and make any edits</li>
          </ol>
        </div>
        <p className="text-sm text-gray-500">💡 <strong>Pro tip:</strong> Use Bulk Import to add many recipes at once — paste one URL per line.</p>
        <p className="text-sm text-gray-500">💡 Proteins and cuisines are auto-tagged so the meal planner knows what&apos;s what.</p>
      </div>
    ),
    action: { href: "/recipes/import", label: "Start Importing →" },
  },
  {
    title: "Step 2: Set Your Rules 📏",
    icon: "📏",
    content: (
      <div className="space-y-3">
        <p>Tell Butler Groceries your dietary preferences. These rules guide all meal suggestions.</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">Pre-loaded rules:</p>
          <ul className="space-y-1 ml-4">
            <li>🍗 Chicken max 2x per week</li>
            <li>🐟 Salmon at least 1x every 2 weeks</li>
            <li>🥩 Red meat max 2x per week</li>
            <li>🔄 No repeating the same recipe within 14 days</li>
            <li>🥬 At least 2 vegetarian dinners per week</li>
          </ul>
        </div>
        <p className="text-sm text-gray-500">Edit, add, or disable rules anytime in <strong>Settings → Rules</strong>.</p>
      </div>
    ),
    action: { href: "/settings", label: "View Rules →" },
  },
  {
    title: "Step 3: Swipe Together 🔥",
    icon: "🔥",
    content: (
      <div className="space-y-3">
        <p>This is the fun part! Swipe on recipes like Tinder — when you both swipe right, it&apos;s a match!</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">How swiping works:</p>
          <ol className="space-y-2 ml-4 list-decimal">
            <li>One of you starts a <strong>Swipe Session</strong></li>
            <li>Choose the vibe: Weeknight, Weekend Special, or Date Night</li>
            <li>Both of you swipe independently (👍 Yes, 👎 Nope, ⭐ Super Like)</li>
            <li>Matches appear when you both liked the same recipe! 🎉</li>
            <li>Plan your matches for specific nights</li>
          </ol>
        </div>
        <p className="text-sm text-gray-500">💡 You can drag cards left/right, or use the buttons below.</p>
        <p className="text-sm text-gray-500">💡 The other person can join the same session anytime — doesn&apos;t have to be simultaneous.</p>
      </div>
    ),
    action: { href: "/swipe", label: "Start Swiping →" },
  },
  {
    title: "Step 4: Plan Your Week 📅",
    icon: "📅",
    content: (
      <div className="space-y-3">
        <p>The weekly planner shows your calendar and helps you fill the open nights.</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">Planner features:</p>
          <ul className="space-y-1 ml-4">
            <li>📆 See the whole week at a glance</li>
            <li>🚫 <strong>Block nights</strong> you&apos;re eating out or traveling</li>
            <li>➕ Manually add recipes to any night</li>
            <li>🧠 Hit <strong>&quot;AI Suggest&quot;</strong> to auto-fill open nights</li>
            <li>📏 Rule status shows if you&apos;re on track</li>
          </ul>
        </div>
        <p className="text-sm text-gray-500">💡 The AI respects all your dietary rules, avoids recent repeats, and picks variety.</p>
      </div>
    ),
    action: { href: "/planner", label: "Open Planner →" },
  },
  {
    title: "Step 5: Cook Together 👨‍🍳",
    icon: "👨‍🍳",
    content: (
      <div className="space-y-3">
        <p>When it&apos;s time to cook, use <strong>Cook-Along Mode</strong> — your phone becomes a cooking assistant!</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">Cook-Along features:</p>
          <ul className="space-y-1 ml-4">
            <li>📱 Big text, one step at a time — easy to read</li>
            <li>⏱ <strong>Built-in timers</strong> — tap to start when a step says &quot;cook for 10 minutes&quot;</li>
            <li>🔆 <strong>Screen stays on</strong> — no phone going dark mid-recipe</li>
            <li>🔢 <strong>Adjust servings</strong> — ingredients scale automatically</li>
            <li>⌨️ Swipe or use arrow keys to navigate steps</li>
            <li>🔔 Timer vibrates &amp; sounds when done</li>
          </ul>
        </div>
        <p className="text-sm text-gray-500">💡 Multiple timers can run simultaneously!</p>
      </div>
    ),
  },
  {
    title: "Step 6: Rate It ⭐",
    icon: "⭐",
    content: (
      <div className="space-y-3">
        <p>After cooking, <strong>both of you rate the recipe independently</strong>. This is what makes Butler Groceries get smarter!</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">Rating details:</p>
          <ul className="space-y-1 ml-4">
            <li>⭐ Rate 1-5 stars</li>
            <li>🔄 Would you make it again?</li>
            <li>📝 Add notes (&quot;needs more garlic&quot;, &quot;Jill loved it&quot;)</li>
            <li>🧠 Ratings feed into the AI taste learner</li>
            <li>👫 See both ratings on the recipe page</li>
          </ul>
        </div>
        <p className="text-sm text-gray-500">💡 After Cook-Along mode finishes, it prompts you to rate automatically.</p>
        <p className="text-sm text-gray-500">💡 You can also rate from any recipe&apos;s detail page.</p>
      </div>
    ),
  },
  {
    title: "Step 7: AI Learns Your Taste 🧠",
    icon: "🧠",
    content: (
      <div className="space-y-3">
        <p>Over time, Butler Groceries builds a <strong>taste profile</strong> for each of you based on your ratings.</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">What it tracks:</p>
          <ul className="space-y-1 ml-4">
            <li>🌍 <strong>Cuisine preferences</strong> — Italian vs Thai vs Mexican</li>
            <li>🥩 <strong>Protein preferences</strong> — Chicken vs salmon vs vegetarian</li>
            <li>📊 <strong>Effort tolerance</strong> — Quick weeknight vs ambitious weekend</li>
            <li>💚 <strong>Agreement map</strong> — Where you and your partner agree/disagree</li>
            <li>💡 <strong>AI Insights</strong> — &quot;You both love Thai but rarely cook it!&quot;</li>
          </ul>
        </div>
        <p className="text-sm text-gray-500">💡 Check your profiles in <strong>Settings → Taste</strong></p>
      </div>
    ),
    action: { href: "/settings", label: "View Taste Profiles →" },
  },
  {
    title: "Bonus: Shopping List 🛒",
    icon: "🛒",
    content: (
      <div className="space-y-3">
        <p>Once your week is planned, generate a smart shopping list with one tap!</p>
        <div className="card p-4 bg-brand-50">
          <p className="font-semibold mb-2">Shopping list magic:</p>
          <ul className="space-y-1 ml-4">
            <li>🧮 <strong>Aggregates ingredients</strong> — 3 recipes need onions? Just shows &quot;Onions (combined amount)&quot;</li>
            <li>🥫 <strong>Subtracts pantry staples</strong> — Salt, oil, garlic? Already got &apos;em</li>
            <li>🏪 <strong>Organized by aisle</strong> — Produce, dairy, meat, pantry</li>
            <li>☑️ <strong>Shared checklist</strong> — Both of you check off items at the store</li>
          </ul>
        </div>
        <p className="text-sm text-gray-500">💡 Manage your pantry staples in <strong>Settings → Pantry</strong></p>
      </div>
    ),
    action: { href: "/shopping", label: "View Shopping List →" },
  },
  {
    title: "You're All Set! 🎉",
    icon: "🎉",
    content: (
      <div className="space-y-3">
        <p className="text-lg">Start by importing 10-15 recipes you love, then try a Swipe session together!</p>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <Link href="/recipes/import" className="card p-4 text-center hover:shadow-md transition-shadow">
            <div className="text-2xl mb-1">📥</div>
            <div className="text-sm font-medium">Import Recipes</div>
          </Link>
          <Link href="/swipe" className="card p-4 text-center hover:shadow-md transition-shadow">
            <div className="text-2xl mb-1">🔥</div>
            <div className="text-sm font-medium">Start Swiping</div>
          </Link>
          <Link href="/planner" className="card p-4 text-center hover:shadow-md transition-shadow">
            <div className="text-2xl mb-1">📅</div>
            <div className="text-sm font-medium">Plan Week</div>
          </Link>
          <Link href="/shopping" className="card p-4 text-center hover:shadow-md transition-shadow">
            <div className="text-2xl mb-1">🛒</div>
            <div className="text-sm font-medium">Shopping List</div>
          </Link>
        </div>
        <div className="text-center mt-4">
          <Link href="/" className="btn-primary">Go to Dashboard →</Link>
        </div>
      </div>
    ),
  },
];

export default function GuidePage() {
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  return (
    <div className="max-w-2xl mx-auto py-4">
      {/* Progress */}
      <div className="flex items-center gap-1 mb-6">
        {STEPS.map((_, i) => (
          <button
            key={i}
            onClick={() => setStep(i)}
            className={`h-1.5 flex-1 rounded-full transition-all ${
              i <= step ? 'bg-brand-500' : 'bg-gray-200'
            }`}
          />
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -30 }}
          transition={{ duration: 0.2 }}
        >
          {/* Card */}
          <div className="card p-6">
            <div className="text-center mb-4">
              <span className="text-5xl">{current.icon}</span>
            </div>
            <h2 className="text-2xl font-bold text-center mb-4">{current.title}</h2>
            {current.content}
          </div>

          {/* Action button */}
          {'action' in current && current.action && (
            <div className="text-center mt-4">
              <Link href={current.action.href} className="text-brand-500 hover:text-brand-600 font-medium">
                {current.action.label}
              </Link>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-6">
        <button
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="btn-secondary disabled:opacity-30"
        >
          ← Back
        </button>
        <span className="text-sm text-gray-400">{step + 1} of {STEPS.length}</span>
        <button
          onClick={() => setStep(Math.min(STEPS.length - 1, step + 1))}
          disabled={step === STEPS.length - 1}
          className="btn-primary disabled:opacity-30"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
