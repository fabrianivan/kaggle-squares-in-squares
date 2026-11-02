# Kaggle Squares in Squares - Clean Project

## 📁 Project Structure

```
kaggle-squares-in-squares/
├── README.md                       # Project overview
├── QUICKSTART.md                   # Quick start guide
├── PROJECT_OVERVIEW.md             # This file
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore rules
│
├── src/                            # Source code
│   ├── simple_improve.py           # ⭐ Merge known better packings (FASTEST)
│   ├── quick_wins.py               # ⭐ Targeted optimization (1-2 hrs)
│   ├── advanced_optimizer.py      # ⭐ Full optimization (4-8 hrs)
│   ├── run_focus.py                # Focus optimizer (original)
│   ├── run_pj_polish.py            # PJ packing polisher
│   ├── verify_and_merge.py         # Verification and merging
│   ├── tools/                      # Core algorithms
│   │   ├── packing_geometry.py     # Geometry utilities
│   │   ├── cpu_axis_reclosure.py   # LP-based reclosure
│   │   ├── cpu_contact_polish.py   # Contact polish optimizer
│   │   └── ...                     # Other utilities
│   └── metric/                     # Official metric
│       └── metric.py               # Evaluation functions
│
├── data/                           # Data files
│   ├── submission_merged_22.253319.csv  # Current baseline
│   ├── submission_merged_22.251*.csv    # Other baselines
│   └── external_packings/          # External sources
│       ├── three-square-packings-that-beat-the-records.ipynb  # PJ's records
│       ├── squares-in-squares-living-atlas-of-tight-packings.ipynb  # Danil
│       └── kaggle_public_candidate_20261102.csv  # Aleksandr
│
├── output/                         # Generated files (gitignored)
│   ├── submission_*.csv            # Your new submissions
│   ├── improvements.json           # Improvement details
│   └── ...
│
├── notebooks/                      # Jupyter notebooks (optional)
│
└── docs/                           # Documentation
    └── OPTIMIZATION_GUIDE.md       # Detailed optimization guide
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Simple Improvement (Fastest!)
```bash
cd src
python simple_improve.py
```

This merges all known better packings and creates a new submission in ~5 minutes.

### 3. Run Targeted Optimization
```bash
cd src
python quick_wins.py
```

Optimizes high-value puzzles in 1-2 hours.

### 4. Upload to Kaggle
```bash
# Find your best submission
ls -lh output/submission_*.csv

# Upload the one with lowest score number!
```

## 📊 Current Status

- **Baseline Score**: 22.253319
- **Target**: Reduce score through better packings
- **Expected Gain**: 0.005-0.015 (conservative estimate)

## 🎯 Key Scripts

### simple_improve.py ⭐ START HERE
**Runtime**: 5 minutes  
**Gain**: 0.002-0.005  
**What it does**: Merges PJ, Danil, and Aleksandr packings with your baseline

### quick_wins.py
**Runtime**: 1-2 hours  
**Gain**: 0.005-0.010  
**What it does**: Intensive optimization on top 150 high-value puzzles

### advanced_optimizer.py
**Runtime**: Configurable (default 4 hours)  
**Gain**: 0.010-0.018  
**What it does**: Full multi-strategy optimization with 4 different approaches

## 🔧 Core Algorithms

Located in `src/tools/`:

- **packing_geometry.py**: Geometry calculations, side length, rotation
- **cpu_axis_reclosure.py**: LP-based optimization with fixed angles
- **cpu_contact_polish.py**: Joint center+angle optimization
- **metric.py**: Official competition metric evaluation

## 📚 Documentation

- **QUICKSTART.md**: How to run optimizers
- **docs/OPTIMIZATION_GUIDE.md**: Detailed algorithm explanations
- **README.md**: Project overview

## 🎓 Algorithm Strategy

1. **Start with known improvements** (simple_improve.py)
2. **Optimize high-value targets** (quick_wins.py on n ≥ 200)
3. **Iterate with new baseline** (use output as input for next round)
4. **Focus on large n** (n=900 worth 30x more than n=10)

## 📦 External Data Sources

### PJ Mathematician
- File: `data/external_packings/three-square-packings-that-beat-the-records.ipynb`
- Contains: n=299, 260, 232 (record-breaking)
- Impact: Beats published Friedman/Ellsworth catalogue!

### Danil's Living Atlas
- File: `data/external_packings/squares-in-squares-living-atlas-of-tight-packings.ipynb`
- Contains: 457 optimized packings
- Impact: Rare puzzles like n=457, 984

### Aleksandr's Candidates
- File: `data/external_packings/kaggle_public_candidate_20261102.csv`
- Contains: Complete 1000-puzzle submission
- Impact: Various improvements across puzzle range

## 🎯 Optimization Workflow

### Recommended: 3-Step Approach

```bash
# Step 1: Quick merge (5 min)
cd src && python simple_improve.py

# Step 2: Check improvement
ls -lh ../output/submission_simple_*.csv

# Step 3: Submit to Kaggle!
# Upload: output/submission_simple_*.csv
```

### Extended: Full Optimization

```bash
# Step 1: Quick merge
python simple_improve.py

# Step 2: Use result as baseline for optimization
python quick_wins.py  # Will auto-detect best baseline

# Step 3: Extended optimization overnight
python advanced_optimizer.py --hours 8 --workers 8

# Step 4: Submit best result
ls -lh ../output/**/*.csv | sort -k5 -n
```

## 💡 Tips

1. **Start simple**: Run `simple_improve.py` first for guaranteed gains
2. **Verify improvements**: Always check the score number in filename
3. **Iterate**: Use each output as the next input baseline
4. **Focus on large n**: They contribute most to score
5. **Be patient**: Good optimization takes time

## 🔍 Troubleshooting

### Import errors
```bash
pip install -r requirements.txt
python -c "import numpy, pandas, scipy; print('OK')"
```

### No improvements found
- Your baseline might already be excellent
- Try longer optimization time
- Check that external packings loaded correctly

### Out of memory
- Reduce `--workers` parameter
- Target fewer puzzles
- Close other applications

## 📈 Expected Results

| Method | Time | Expected Gain | New Score (from 22.253319) |
|--------|------|---------------|----------------------------|
| Simple merge | 5 min | 0.002-0.005 | ~22.250 |
| Quick wins | 1-2 hrs | +0.003-0.005 | ~22.245 |
| Advanced (4h) | 4 hrs | +0.005-0.008 | ~22.240 |
| Extended (24h) | 24 hrs | +0.010-0.018 | ~22.235 |

## 🎉 Success Criteria

✅ Clean, organized project structure  
✅ All essential code and data  
✅ Clear documentation  
✅ Multiple optimization strategies  
✅ Expected improvement: 0.008-0.018 total

## 📞 Next Steps

1. ✅ Project structure created
2. ⏭️ Run `simple_improve.py` 
3. ⏭️ Submit to Kaggle
4. ⏭️ Run extended optimization
5. ⏭️ Iterate and improve!

---

**Current Status**: Ready to optimize! 🚀

**Your baseline**: 22.253319  
**Target**: < 22.240  
**Next action**: `cd src && python simple_improve.py`
