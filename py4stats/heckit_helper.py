#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import numpy as np
from py4etrics.heckit import Heckit

import statsmodels.formula.api as smf
import patsy

from py4stats import bilding_block as bild # py4stats のプログラミングを補助する関数群
from py4stats import regression_tools as reg

from functools import singledispatch


# ### 回帰式を使った Heckit のインターフェース

# In[ ]:


def Heckit_from_formula(selection, outcome, data, **kwargs):
  # ステップ1：第１段階の説明変数
  y_select, exog_select = patsy.dmatrices(
      selection, data, return_type = 'dataframe',
      NA_action=patsy.NAAction(NA_types=[]) # 欠測値の除外を止める
      )

  # ステップ2：第２段階の説明変数と被説明変数
  endog, exog_outcome = patsy.dmatrices(
      outcome, data, return_type = 'dataframe',
      NA_action=patsy.NAAction(NA_types=[]) # 欠測値の除外を止める
      )

  endog_name = endog.columns.to_list()[0]

  model = Heckit(endog[endog_name], exog_outcome, exog_select, **kwargs)
  return model, exog_outcome, exog_select


# ## `HeckitResults` 用の `tidy()` メソッド

# In[ ]:


# regression_tools.tdy() にメソッドを後付けする実験的試み
from py4etrics.heckit import HeckitResults

@reg.tidy.register(HeckitResults)
def tidy_heckit(
    model,
    name_selection = None,
    name_outcome = None,
    conf_level = 0.95
    ):
  tidy_outcome = reg.tidy_regression(
      model,
      name_of_term = name_outcome,
      conf_level = conf_level
      )

  tidy_outcome.index = 'O: ' + tidy_outcome.index.to_series()

  tidy_select = reg.tidy_regression(
      model.select_res,
      name_of_term = name_selection,
      conf_level = conf_level
      )

  tidy_select.index = 'S: ' + tidy_select.index.to_series()

  res = pd.concat([tidy_outcome, tidy_select])
  return res


# ### 限界効果を推定する関数

# In[ ]:


from scipy.stats import norm

def finv_mills(x): return norm.pdf(x) / norm.cdf(x)

# 適切なダミー変数かどうかを判定する関数
def is_dummy(x): return x.isin([0, 1]).all(axis = 'index') & (x.nunique() == 2)

def f_d_lambda(var_name, Z, gamma, beta_lambda):
  z1 = Z.mean().copy()
  z0 = z1.copy()
  z1[var_name] = 1
  z0[var_name] = 0
  res = beta_lambda * (finv_mills(z1 @ gamma) - finv_mills(z0 @ gamma))
  return res

def f_d_log_cdf(var_name, Z, gamma, beta_lambda):
  z1 = Z.mean().copy()
  z0 = z1.copy()
  z1[var_name] = 1
  z0[var_name] = 0
  res = (np.log(norm.cdf(z1 @ gamma)) - np.log(norm.cdf(z0 @ gamma)))
  return res


# In[ ]:


from py4etrics.heckit import HeckitResults

def heckitmfx_compute(
    model,
    exog_select,
    exog_outcome,
    exponentiate = False,
    params = None):

  model = bild.type_checke(model, HeckitResults, 'model')

  # 回帰係数の抽出 --------------
  if params is not None:
    # 回帰係数が指定された場合の処理（デルタ法の実装用）
    n_gamma = int(model.select_res.df_model + 1)
    beta = pd.Series(params[n_gamma:], exog_outcome.columns)
    gamma = pd.Series(params[:n_gamma], exog_select.columns)
  else:
    beta = pd.Series(model.params, exog_outcome.columns)
    gamma = pd.Series(model.select_res.params, exog_select.columns)

  beta.name = 'beta'
  gamma.name = 'gamma'

  # 逆ミルズ比の回帰係数 --------------
  beta_lambda = model.params_inverse_mills

  est = pd.merge(beta[1:], gamma[1:], how='outer', left_index=True, right_index=True)
  # 賃金関数で使われていない変数については beta に nan が発生するため、0で置換します。
  est[est.isna()] = 0

  # 連続変数用の処理--------------
  # alpha = model.select_res.fittedvalues
  alpha = exog_select @ gamma

  lambda_value = finv_mills(alpha)

  delta = lambda_value * (lambda_value + alpha)
  selection = gamma * lambda_value.mean()
  ei_2 = gamma * beta_lambda * delta.mean()

  #  ダミー変数用の処理 --------------
  dummy_vars = is_dummy(exog_select)

  if(dummy_vars.sum() >= 1):

    d_lambda_val = [
        f_d_lambda(var_name, exog_select, gamma, beta_lambda)
        for var_name in dummy_vars[dummy_vars].index.to_list()
        ]

    d_log_cdf_val = [
        f_d_log_cdf(var_name, exog_select, gamma, beta_lambda)
        for var_name in dummy_vars[dummy_vars].index.to_list()
        ]

    ei_2[dummy_vars] = d_lambda_val
    selection[dummy_vars] = d_log_cdf_val
  # 限界効果の計算 ---------------------
  est['conditional'] = est['beta'] - ei_2
  est['selection'] = selection
  est['unconditional'] = est['conditional'] + est['selection']
  est = est.loc[:, ['unconditional', 'conditional', 'selection', 'beta', 'gamma']]

  if(exponentiate):
    est.loc[:, ['unconditional', 'conditional', 'selection', 'beta']] = \
    log_to_pct(est.loc[:, ['unconditional', 'conditional', 'selection', 'beta']])

  est.index.name  = 'term'
  return est


# In[ ]:


def log_to_pct(x): return 100 * (np.exp(x) - 1)


# ### デルタ法により限界効果の標準誤差を推定する関数

# In[ ]:


def jacobian(f, x, h=0.00001, *args):
    J = []
    x = np.array(x).astype(float)
    for i in range(len(x)):
        x1 = x.copy()
        x0 = x.copy()
        x1[i] = x[i] + h
        x0[i] = x[i] - h
        J.append((f(x1, *args) - f(x0, *args)) / (2 * h))
    return np.column_stack(J)
    return J


# In[ ]:


from scipy.stats import norm

def heckitmfx(
    model,
    exog_select,
    exog_outcome,
    type_estimate = 'unconditional',
    exponentiate = False,
    alpha = 0.05
    ):

  type_estimate = bild.arg_match(
      type_estimate, arg_name = 'type_estimate',
       values = ['unconditional', 'conditional', 'selection']
      )

  # 限界効果の推定
  estimate = heckitmfx_compute(
      model, exog_select, exog_outcome,
      exponentiate = exponentiate
      ).loc[:, type_estimate]

  # 共分散行列の作成
  vcv1 = model.select_res.cov_params()
  vcv2 = model.cov_params()

  O = np.zeros(shape = (vcv1.shape[0], vcv2.shape[0]))

  vcv = np.block([[vcv1, O], [O.T, vcv2]])

  # ヤコブ行列の計算
  J_mat = jacobian(
      f = lambda x : heckitmfx_compute(
          model, exog_select, exog_outcome,
          params = x, exponentiate = exponentiate
          ).loc[:, type_estimate],
      x = np.append(model.select_res.params, model.params)
      )
  # デルタ法による標準誤差の推定
  std_err = np.sqrt(np.diag(J_mat @ vcv @ J_mat.T))

  # Z統計量の推定値を計算
  statistic = estimate / std_err
  z_alpha = norm.isf(alpha/2)

  # 結果の出力
  res = pd.DataFrame({
    'type':type_estimate,
    'estimate':estimate,
    'std_err':std_err,
    'statistic': statistic,
    'p_value': 2 * norm.sf(statistic.abs()), # 両側p-値
    'conf_lower': estimate - z_alpha * std_err,
    'conf_higher': estimate + z_alpha * std_err
    })

  return res

