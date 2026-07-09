## REPL boot — idle state

```
$ baymax
Cycle: Jun 26 – Jul 25   (day 10 of 30)
> 
```
That's it. No summary, no "you have 3 budgets," nothing until asked — the agent starts quiet.

## Session history

The REPL keeps command history for the current session.

```
> $45 groceries
✓ $45.00 — groceries  [Groceries]

> report groceries
Groceries — Jun 26–Jul 25
  $403 of $400 (101%) · 15 expenses · avg $26.87
  Largest: Costco $91, Whole Foods $64, Trader Joe's $58

> history
1  $45 groceries
2  report groceries
3  history
```

Use the up arrow to recall previous commands and the down arrow to move forward through the session history, like a shell.

## The core loop: minimal log

```
> $45 groceries
✓ $45.00 — groceries  [Groceries]

> $22 parking downtown
✓ $22.00 — parking downtown
```
Second one gets no category — "parking downtown" doesn't match anything learned yet, and that's a fine terminal state, not a gap to flag.

## Adding a flag

```
> $12 coffee, one-off
✓ $12.00 — coffee  #one-off
```

## Optimistic parse, then a correction

```
> $18 target
✓ $18.00 — target  [Shopping]

> no, that one's for the emergency fund goal
✓ updated — $18.00 — target  [Shopping]  → Emergency Fund
```
No "are you sure" — the correction just lands. Same pattern for a typo'd amount:
```
> $45 groceries
✓ $45.00 — groceries  [Groceries]

> oops, 54 not 45
✓ updated — $54.00 — groceries  [Groceries]
```

## Budgeted category — live balance, ambient

```
> $85 groceries
✓ $85.00 — groceries  [Groceries]
  Groceries: $233 left of $400 this cycle
```
Compare to the parking example above — no second line there, because there's no budget to report against. The line only exists when it's true and useful.

## Linking to a goal — clean match vs. the suggest-first exception

Unambiguous:
```
> $50 karate class, kid goal
✓ $50.00 — karate class  [Kids]  → Raise a strong, resilient kid
```
Ambiguous — this is the one place a numbered list is allowed:
```
> $40 books, learning goal
Which goal?
  1. Raise a strong, resilient kid
  2. Get promoted this year
  3. Don't link to a goal
> 1
✓ $40.00 — books  [Kids]  → Raise a strong, resilient kid
```
No existing match at all:
```
> $200 flight deposit, family trip fund
No goal called "family trip fund" yet:
  1. Save for family trip
  2. Create new goal: "family trip fund"
  3. Don't link to a goal
> 1
✓ $200.00 — flight deposit  [Travel]  → Save for family trip
```

## The one interruption the agent's allowed to make

```
> $60 groceries
✓ $60.00 — groceries  [Groceries]

⚠ Groceries — 82% of budget ($328 of $400)
   Jun 27  farmers market      $22
   Jun 29  Whole Foods         $64
   Jul 01  Costco              $91
   Jul 03  Trader Joe's        $58
   Jul 05  groceries           $60
```
Later that cycle, second and last ping:
```
> $75 groceries
✓ $75.00 — groceries  [Groceries]

⚠ Groceries — over budget: $403 of $400 (101%)
   [full list]
```
After this, groceries can keep being logged all cycle with no more pings — the budget for this category is spent.

## Backdated entry crossing a cycle boundary

```
> 6/20 $200 car repair
✓ $200.00 — car repair  [Auto]
  ↳ logged to cycle May 26 – Jun 25 (closed)
```

## Answering questions

```
> how much on groceries this cycle?
Groceries: $403.00 of $400 (101%) — 15 expenses

> what's left in eating out?
Eating Out doesn't have a budget this cycle.

> what did we put toward the resilient kid goal this cycle?
$90.00 across 2 expenses — karate class $50, books $40
```

## Budget recommendation

```
> suggest a groceries budget
Last 3 cycles: $380, $410, $395 — avg $395
Suggest $400/cycle. Set it?
> yes
✓ Groceries budget set to $400/cycle
```

## Setting budgets

Create a new category with a budget:
```
> set groceries budget to $600
✓ Created [Groceries] — budget $600/cycle
```

Existing category that had no budget:
```
> set eating out budget to $150
✓ [Eating Out] budget set to $150/cycle
```

Changing an existing budget:
```
> set groceries budget to $600
✓ [Groceries] budget updated: $600/cycle (was $400/cycle)
```

Removing a budget entirely:
```
> remove groceries budget
✓ [Groceries] — budget removed (was $600/cycle)
```

## Reports

```
> report groceries
Groceries — Jun 26–Jul 25
  $403 of $400 (101%) · 15 expenses · avg $26.87
  Largest: Costco $91, Whole Foods $64, Trader Joe's $58

> report goal resilient kid
Raise a strong, resilient kid
  This cycle: $90 across 2 expenses
  All-time: $890 across 14 expenses (since Mar 2026)
```
That "all-time" line is doing real work — it's the CLI's way of showing goals cross cycle boundaries when everything else doesn't.

---

**Formatting conventions used above** (all up for debate): `✓` confirm, `[Category]` brackets, `#flag`, `→ Goal`, `↳` cross-cycle note, `⚠` the rare interruption.
