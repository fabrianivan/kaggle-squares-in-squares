# Quick Start Guide

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Verify installation:**
```bash
cd src
python -c "import numpy, pandas, scipy; print('All dependencies installed!')"
```

## Run Optimization

### Option 1: Quick Improvement (5 minutes)
Merge all known better packings without optimization:

```bash
cd src
python simple_improve.py
```

**Output**: `output/submission_simple_*.csv`

### Option 2: Targeted Optimization (1-2 hours)
Focus on high-value puzzles:

```bash
cd src
python quick_wins.py
```

**Output**: `output/quick_wins_out/submission_*.csv`

### Option 3: Full Optimization (4-8 hours)
Comprehensive multi-strategy optimization:

```bash
cd src
python advanced_optimizer.py --hours 4 --workers 8
```

**Output**: `output/advanced_out/submission_*.csv`

## Check Results

All output files are saved in the `output/` directory.

Upload the best submission to Kaggle!

## Documentation

See `docs/OPTIMIZATION_GUIDE.md` for detailed information.
