# 配線のインピーダンスを 2D 差分法 (準 TEM、ラプラス方程式) で計算する (2026-11-21)
#   積層 JLC08161H-3313 (8層 1.6mm)。JLCPCB の計算ツールが使えなかったための自前計算。
#   単線: Z0 = 1 / (c * sqrt(C * C_air))。差動: 奇モードで Zdiff = 2 * Zodd。
#   誘電率 (JLCPCB の公表値ベース): 3313 = 4.1、2116 = 4.16、コア = 4.4 (仮定)、ソルダーレジスト 3.8 (厚さ 0.02)。
# usage: python impedance_fd.py
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

C0 = 299792458.0
EPS0 = 8.854e-12
D = 0.005  # 格子 (mm)

ER_3313, ER_2116, ER_CORE, ER_SM = 4.1, 4.16, 4.4, 3.8
T_OUT, T_IN = 0.035, 0.0152  # 外層 (1oz、メッキ前)、内層 (0.5oz)


def build(kind, w, s, diff):
    """kind = 'micro' (L1/L8) or 'strip' (L3/L6)。格子の ε マップと導体マスクを返す"""
    half = 1.6 if kind == 'micro' else 1.2
    nx = int(round(2 * half / D)) + 1
    xs = (np.arange(nx) - (nx - 1) / 2) * D
    if kind == 'micro':
        h, t = 0.0994, T_OUT
        top = h + t + 1.5
        ny = int(round(top / D)) + 1
        ys = np.arange(ny) * D
        eps = np.ones((ny, nx))
        eps[ys < h] = ER_3313
        tb, tt = h, h + t
    else:
        hb, h1, t = 0.357, 0.100, T_IN  # 下 = 2116×3 (L4/L5 電源面)、上 = コア 0.1 (L2/L7 GND)
        top = hb + h1
        ny = int(round(top / D)) + 1
        ys = np.arange(ny) * D
        eps = np.full((ny, nx), ER_2116)
        eps[ys >= hb] = ER_CORE
        tb, tt = hb - t, hb
    cond = np.zeros((ny, nx), dtype=np.int8)  # 0 = なし、1 = +V、2 = -V (差動の相手)
    yin = (ys >= tb - 1e-9) & (ys <= tt + 1e-9)
    if diff:
        c1 = -(s / 2 + w / 2)
        c2 = +(s / 2 + w / 2)
        for c, val in ((c1, 1), (c2, 2)):
            xin = np.abs(xs - c) <= w / 2 + 1e-9
            cond[np.ix_(yin, xin)] = val
    else:
        xin = np.abs(xs) <= w / 2 + 1e-9
        cond[np.ix_(yin, xin)] = 1
    if kind == 'micro':
        # ソルダーレジスト: 誘電体の上 0.02、導体の上と横も 0.02 で覆う
        sm = np.zeros_like(eps, dtype=bool)
        sm[(ys >= h) & (ys < h + 0.02)] = True
        ci = np.argwhere(cond > 0)
        if len(ci):
            iy0, iy1 = ci[:, 0].min(), ci[:, 0].max()
            k = int(round(0.02 / D))
            for val in (1, 2):
                cc = np.argwhere(cond == val)
                if not len(cc):
                    continue
                ix0, ix1 = cc[:, 1].min(), cc[:, 1].max()
                sm[iy0:iy1 + k + 1, max(ix0 - k, 0):ix1 + k + 1] = True
        eps[sm & (eps == 1.0)] = ER_SM
    return eps, cond


def energy(eps, cond, vpos, vneg):
    ny, nx = eps.shape
    N = ny * nx
    idx = np.arange(N).reshape(ny, nx)
    fixed = np.zeros((ny, nx), dtype=bool)
    val = np.zeros((ny, nx))
    fixed[0, :] = True  # 下の面 (GND)
    fixed[-1, :] = True  # 上の面 (ストリップライン) / 遠方 (マイクロストリップ)
    fixed[cond == 1] = True
    val[cond == 1] = vpos
    fixed[cond == 2] = True
    val[cond == 2] = vneg
    # セル中心の ε を辺の ε (平均) にして 5 点差分。左右の端はノイマン
    rows, cols, data = [], [], []
    b = np.zeros(N)
    ex = 0.5 * (eps[:, 1:] + eps[:, :-1])  # x 方向の辺 (ny, nx-1)
    ey = 0.5 * (eps[1:, :] + eps[:-1, :])  # y 方向の辺 (ny-1, nx)
    diag = np.zeros((ny, nx))
    for (a_sl, b_sl, e) in (((slice(None), slice(1, None)), (slice(None), slice(None, -1)), ex),
                            ((slice(1, None), slice(None)), (slice(None, -1), slice(None)), ey)):
        ia = idx[a_sl].ravel()
        ib = idx[b_sl].ravel()
        ev = e.ravel()
        diag.ravel()[ia] += 0  # placeholder
        np.add.at(diag.ravel(), ia, ev)
        np.add.at(diag.ravel(), ib, ev)
        rows += [ia, ib]
        cols += [ib, ia]
        data += [-ev, -ev]
    rows = np.concatenate(rows)
    cols = np.concatenate(cols)
    data = np.concatenate(data)
    A = sp.csr_matrix((data, (rows, cols)), shape=(N, N)) + sp.diags(diag.ravel())
    fr = fixed.ravel()
    free = np.where(~fr)[0]
    fx = np.where(fr)[0]
    vf = val.ravel()[fx]
    Aff = A[free][:, free]
    rhs = -A[free][:, fx] @ vf
    v = np.zeros(N)
    v[fx] = vf
    v[free] = spl.spsolve(Aff.tocsc(), rhs)
    V = v.reshape(ny, nx)
    # 静電エネルギー (単位長さ、D は打ち消し合う: 2D なので ∑ ε (ΔV)^2 / 2)
    W = 0.5 * EPS0 * (np.sum(ex * (V[:, 1:] - V[:, :-1]) ** 2) + np.sum(ey * (V[1:, :] - V[:-1, :]) ** 2))
    return W


def z(kind, w, s=0.0, diff=False):
    eps, cond = build(kind, w, s, diff)
    air = np.ones_like(eps)
    if diff:
        C = energy(eps, cond, 1, -1)  # W = 2 * (1/2) Codd V^2 → Codd = W
        Ca = energy(air, cond, 1, -1)
        zo = 1 / (C0 * np.sqrt(C * Ca))
        return 2 * zo, np.sqrt(C / Ca)
    C = 2 * energy(eps, cond, 1, 0)
    Ca = 2 * energy(air, cond, 1, 0)
    return 1 / (C0 * np.sqrt(C * Ca)), np.sqrt(C / Ca)


if __name__ == '__main__':
    import sys
    print('単線 (Z0, √εeff)')
    for kind in ('micro', 'strip'):
        for w in (0.09, 0.10, 0.11, 0.12, 0.14, 0.16, 0.18, 0.20):
            zz, ee = z(kind, w)
            print(f'  {kind:5s} w={w:.3f}  Z0={zz:6.1f}  sqrt(eeff)={ee:.3f}', flush=True)
    print('差動 (Zdiff)')
    for kind in ('micro', 'strip'):
        for s in (0.10, 0.127, 0.15, 0.20):
            for w in (0.09, 0.10, 0.12, 0.14):
                zz, ee = z(kind, w, s, True)
                print(f'  {kind:5s} w={w:.3f} s={s:.3f}  Zdiff={zz:6.1f}', flush=True)
