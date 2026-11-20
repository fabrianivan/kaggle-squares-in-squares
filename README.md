# Kaggle Squares in Squares - Optimization Project

Clean, organized project for optimizing square packing solutions.

## Structure

```
kaggle-squares-in-squares/
├── src/                    # Source code
│   ├── simple_improve.py   # Merge known better packings
│   ├── quick_wins.py       # Fast targeted optimization
│   ├── advanced_optimizer.py # Full multi-strategy optimizer
│   ├── run_focus.py        # Original focus optimizer
│   ├── run_pj_polish.py    # PJ packing polisher
│   ├── verify_and_merge.py # Verification and merging
│   ├── tools/              # Core optimization algorithms
│   └── metric/             # Official metric evaluation
├── data/                   # Data files
│   ├── submission_*.csv    # Baseline submissions
│   └── external_packings/  # PJ, Danil, Aleksandr packings
├── notebooks/              # Jupyter notebooks (optional)
├── output/                 # Generated output files
└── docs/                   # Documentation
    └── OPTIMIZATION_GUIDE.md
```

## Quick Start

### 1. Merge Known Improvements
```bash
cd src
python simple_improve.py
```

### 2. Targeted Optimization (1-2 hours)
```bash
cd src
python quick_wins.py
```

### 3. Full Optimization (4-8 hours)
```bash
cd src
python advanced_optimizer.py --hours 8 --workers 8
```

## Current Score

- Best locally certified candidate: **22.106285682524** — certified by the official interval metric with 0 rejected puzzles and 500,500 rows. This improves the previously reported 22.1774646631 score by 0.0711789806. The candidate CSV and validation report are local, ignored output artifacts; they are not included in this repository.

Goal: Reduce through better packings

## Key Files

- **simple_improve.py**: Fastest way to get improvements by merging external packings
- **quick_wins.py**: Focused optimization on high-value targets
- **advanced_optimizer.py**: Comprehensive multi-strategy optimization
- **tools/**: Core algorithms (axis_reclosure, contact_polish, packing_geometry)

## Documentation

See `docs/OPTIMIZATION_GUIDE.md` for detailed usage instructions.

## Algorithm Credits

- PJ Mathematician: Record-breaking packings (n=299, 260, 232)
- Danil: Living atlas of 457 tight packings
- Aleksandr: Public candidate packings
- Contact Polish: Adapted from lightningv08's CUDA implementation (Apache 2.0)
