"""Multiple-choice allocation from empirical queue-response curves."""
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


def even_allocation(sites, budget, max_crews):
    if sites <= 0 or not 0 <= budget <= sites*max_crews:
        raise ValueError("Crew budget outside feasible range")
    allocation = np.full(sites, budget//sites, dtype=int)
    allocation[:budget % sites] += 1
    return allocation


def optimize(loss, budget, time_limit=30.0):
    """Choose one crew count per site. Finite options, no interpolation."""
    loss = np.asarray(loss, dtype=float)
    if loss.ndim != 2 or min(loss.shape) < 1 or not np.isfinite(loss).all() or (loss < 0).any():
        raise ValueError("Finite nonnegative site-by-crew response table required")
    sites, options = loss.shape
    if not isinstance(budget, int) or not 0 <= budget <= sites*(options-1):
        raise ValueError("Invalid integer crew budget")
    a = lil_matrix((sites+1, sites*options))
    for i in range(sites):
        a[i, i*options:(i+1)*options] = 1
        a[-1, i*options:(i+1)*options] = np.arange(options)
    lower = np.r_[np.ones(sites), 0]
    upper = np.r_[np.ones(sites), budget]
    result = milp(loss.ravel(), integrality=np.ones(loss.size),
                  bounds=Bounds(0, 1), constraints=LinearConstraint(a.tocsr(), lower, upper),
                  options={"time_limit": time_limit, "mip_rel_gap": 0.0})
    if result.x is None:
        raise RuntimeError("No allocation incumbent: "+result.message)
    x = result.x.reshape(loss.shape)
    allocation = x.argmax(axis=1)
    if (np.abs(x-np.round(x)) > 1e-6).any() or not np.allclose(x.sum(axis=1), 1) or allocation.sum() > budget:
        raise RuntimeError("Solver returned an invalid allocation")
    return allocation, {
        "status": int(result.status), "message": result.message,
        "objective": float(loss[np.arange(sites), allocation].sum()),
        "mip_gap": float(result.mip_gap), "dual_bound": float(result.mip_dual_bound),
        "variables": int(loss.size), "constraints": sites+1,
        "crews_used": int(allocation.sum()),
    }
