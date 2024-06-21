#!/usr/bin/env python
# coding: utf-8

# # `reg_tools`：回帰分析の結果を要約する関数群

# In[ ]:


# 依存するライブラリーの読込
import pandas as pd
import numpy as np
import scipy as sp
from scipy.stats import t
from scipy.stats import f
from functools import singledispatch
import matplotlib.pyplot as plt

import seaborn as sns
import matplotlib.pyplot as plt

import statsmodels.api as sm
import statsmodels.formula.api as smf

import sys

from py4stats import bilding_block as bild # py4stats のプログラミングを補助する関数群

from functools import singledispatch


# ## 回帰分析の結果をデータフレームに変換する関数

# In[ ]:


from functools import singledispatch

# definition of tidy --------------------------------------------------
@singledispatch
def tidy(x, name_of_term = None, conf_level = 0.95, **kwargs):
  raise NotImplementedError(f'tidy mtethod for object {type(x)} is not implemented.')


# In[ ]:


from statsmodels.iolib.summary import summary_params_frame
from statsmodels.regression.linear_model import RegressionResultsWrapper

@tidy.register(RegressionResultsWrapper)
def tidy_regression(
  x,
  name_of_term = None,
  conf_level = 0.95,
  add_one_sided = False,
  to_jp = False,
  **kwargs
  ):
  bild.assert_float(conf_level, lower = 0, upper = 1, inclusive = 'neither')

  tidied = summary_params_frame(x, alpha = 1 - conf_level, xname = name_of_term)

  tidied.index.name = 'term'

  rename_cols = {
      'coef':'estimate',
      'std err':'std_err',
      't':'statistics', 'P>|t|': 'p_value',
      'Conf. Int. Low': 'conf_lower',
      'Conf. Int. Upp.': 'conf_higher'
  }

  tidied = tidied.rename(columns = rename_cols)

  if add_one_sided:
      tidied = add_one_sided_p_value(x, tidied)

  # 列名を日本語に変換
  if to_jp:
      tidied = tidy_to_jp(tidied, conf_level = 0.95)

  return tidied


# In[ ]:


from statsmodels.stats.contrast import ContrastResults

@tidy.register(ContrastResults)
def tidy_test(
  x,
  conf_level = 0.95,
  **kwargs
  ):
  bild.assert_float(conf_level, lower = 0, upper = 1, inclusive = 'neither')
  if(x.distribution == 'F'):
    tidied = pd.DataFrame({
    'statistics':x.statistic,
    'p_value':x.pvalue,
    'df_denom':int(x.df_denom),
    'df_num':int(x.df_num)
  }, index = ['contrast'])

  else:
    tidied = x.summary_frame(alpha = 1 - conf_level)

    rename_cols = {
        'coef':'estimate',
        'std err':'std_err',
        't':'statistics', 'P>|t|': 'p_value',
        'Conf. Int. Low': 'conf_lower',
        'Conf. Int. Upp.': 'conf_higher'
    }

    tidied = tidied.rename(columns = rename_cols)

  tidied.index.name = 'term'
  return tidied


# ### 片側t-検定

# In[ ]:


from scipy.stats import t
from scipy.stats import norm

# definition of tidy --------------------------------------------------
@singledispatch
def tidy_one_sided(x, conf_level = 0.95, **kwargs):
  raise NotImplementedError(f'tidy mtethod for object {type(x)} is not implemented.')

@tidy_one_sided.register(ContrastResults)
def tidy_one_sided_t_test(x, conf_level = 0.95):
  bild.assert_float(conf_level, lower = 0, upper = 1, inclusive = 'neither')
  tidied = tidy(x)

  # 仮説検定にt分布が用いられている場合
  if(x.distribution == 't'):
    tidied['p_value'] = t.sf(abs(tidied['statistics']), x.dist_args[0])
    t_alpha = t.isf(1 - conf_level, df = x.dist_args[0])
    tidied['conf_lower'] = tidied['estimate'] - t_alpha * tidied['std_err']
    tidied['conf_higher'] = tidied['estimate'] + t_alpha * tidied['std_err']

  # 仮説検定に正規分布が用いられている場合
  elif(x.distribution == 'norm'):
    tidied['p_value'] = norm.sf(abs(tidied['statistics']))
    z_alpha = norm.isf(1 - conf_level)
    tidied['conf_lower'] = tidied['estimate'] - z_alpha * tidied['std_err']
    tidied['conf_higher'] = tidied['estimate'] + z_alpha * tidied['std_err']
  else:
    raise NotImplementedError(f'tidy mtethod for distribution {x.distribution} is not implemented.')

  return tidied

@tidy_one_sided.register(RegressionResultsWrapper)
def tidy_one_sided_regression(x, conf_level = 0.95, null_hypotheses = 0):
  bild.assert_float(conf_level, lower = 0, upper = 1, inclusive = 'neither')
  bild.assert_numeric(null_hypotheses)

  tidied = tidy(x)

  tidied['H_null'] = null_hypotheses

  tidied['statistics'] = (tidied['estimate'] - tidied['H_null']) / tidied['std_err']
  # 仮説検定にt分布が用いられている場合
  if(x.use_t):
    tidied['p_value'] = t.sf(abs(tidied['statistics']), x.df_resid)
    t_alpha = t.isf(1 - conf_level, df = x.df_resid)
    tidied['conf_lower'] = tidied['estimate'] - t_alpha * tidied['std_err']
    tidied['conf_higher'] = tidied['estimate'] + t_alpha * tidied['std_err']
  # 仮説検定に正規分布が用いられている場合
  else:
    tidied['p_value'] = norm.sf(abs(tidied['statistics']))
    z_alpha = norm.isf(1 - conf_level)
    tidied['conf_lower'] = tidied['estimate'] - z_alpha * tidied['std_err']
    tidied['conf_higher'] = tidied['estimate'] + z_alpha * tidied['std_err']

  return tidied


# In[ ]:


from scipy.stats import t
def tidy_to_jp(tidied, conf_level = 0.95):
  tidied = tidied\
      .rename(columns = {
          'term':'説明変数',
          'estimate':'回帰係数', 'std_err':'標準誤差',
          'statistics':'t-値', 'p_value':'p-値',
          'conf_lower': str(int(conf_level*100)) + '%信頼区間下側',
          'conf_higher': str(int(conf_level*100)) + '%信頼区間上側',
          'one_sided_p_value':'片側p-値'
          })

  tidied.index.name = '説明変数'

  return tidied

def add_one_sided_p_value(x, tidied):
      tidied['one_sided_p_value'] = t.sf(abs(tidied['statistics']), x.df_resid)
      return tidied


# `glance()`

# In[ ]:


from statsmodels.regression.linear_model import RegressionResultsWrapper
from statsmodels.discrete.discrete_model import BinaryResultsWrapper, PoissonResultsWrapper, NegativeBinomialResultsWrapper
from functools import singledispatch

@singledispatch
def glance(x):
    raise NotImplementedError(f'glance mtethod for object {type(x)} is not implemented.')

# 一般化線型モデル用のメソッド
@glance.register(BinaryResultsWrapper)
@glance.register(PoissonResultsWrapper)
@glance.register(NegativeBinomialResultsWrapper)
def glance_glm(x):
  res = pd.DataFrame({
      'prsquared':x.prsquared,
      'LL-Null':x.llnull ,
      'df_null':x.nobs - 1,
      'logLik':x.llf,
      'AIC':x.aic,
      'BIC':x.bic,
      'deviance':-2*x.llf,
      'nobs':x.nobs,
      'df': int(x.df_model),
      'df_resid':int(x.df_resid)
  }, index = [0])
  return res

# 線形回帰用のメソッド
@glance.register(RegressionResultsWrapper)
def glance_ols(x):
    res = pd.DataFrame({
        'rsquared':x.rsquared,
        'rsquared_adj':x.rsquared_adj,
        'nobs':int(x.nobs),
        'df':int(x.df_model),
        'sigma':np.sqrt(x.mse_resid),
        'F_values':x.fvalue,
        'p_values':x.f_pvalue,
        'AIC':x.aic,
        'BIC':x.bic
    }, index = [0])
    return res


# In[ ]:


def log_to_pct(est): return 100 * (np.exp(est) - 1)


# ## `reg.compare_ols()`
# 
# ### 概要
# 
# 　`reg.compare_ols()` は計量経済学の実証論文でよく用いられる、回帰分析の結果を縦方向に並べて比較する表をする関数です。
# 　使用方法は次の通りで、`sm.ols()` や `smf.ols()` で作成した分析結果のオブジェクトのリストを代入します。  
# 
# ```python
# penguins = load_penguins() # サンプルデータの読み込み
# 
# fit1 = smf.ols('body_mass_g ~ bill_length_mm + species', data = penguins).fit()
# fit2 = smf.ols('body_mass_g ~ bill_length_mm + bill_depth_mm + species', data = penguins).fit()
# fit3 = smf.ols('body_mass_g ~ bill_length_mm + bill_depth_mm + species + sex', data = penguins).fit()
# 
# compare_tab1 = reg.compare_ols([fit1, fit2, fit3])
# compare_tab1
# ```

# In[ ]:


from statsmodels.regression.linear_model import RegressionResultsWrapper
from varname import argname

def assert_reg_reuslt(x):
  x = pd.Series(x)
  condition =  x.apply(lambda x: isinstance(x, (RegressionResultsWrapper))).all()
  assert condition, f"Argment '{argname('x')}' must be of type '{RegressionResultsWrapper}'."


# In[ ]:


import pandas.api.types

def compare_ols(
    list_models,
    model_name = None,
    subset = None,
    stats = 'std_err',
    add_stars = True,
    stats_glance = ['rsquared_adj', 'nobs', 'df'],
    digits = 4,
    table_style = 'two_line',
    line_break = '\n',
    **kwargs
    ):
  """複数のモデルを比較する表を作成する関数"""
  assert pandas.api.types.is_list_like(list_models), "argument 'list_models' is must be a list of models."
  assert_reg_reuslt(list_models)

  tidy_list = [tidy(mod) for mod in list_models]

  # モデル名が指定されていない場合、連番を作成する
  if model_name is None:
      model_name = [f'model {i + 1}' for i in range(len(tidy_list))]

  # lineup_models() を適用してモデルを比較する表を作成
  res = lineup_models(
          tidy_list, model_name = model_name,
          digits = digits, stats = stats,
          add_stars = add_stars, table_style = table_style,
          subset = subset,
          line_break = line_break,
          **kwargs
      )
  res.index.name = 'term'
  # 表の下部にモデルの当てはまりに関する統計値を追加
  if stats_glance is not None: # もし stats_glance が None なら統計値を追加しない
      res2 = make_glance_tab(
          list_models,
          model_name = model_name,
          stats_glance = stats_glance,
          digits = digits
          )
      res = pd.concat([res, res2])

  return res


# In[ ]:


def make_glance_tab(
    list_models,
    model_name = None,
    stats_glance = ['rsquared_adj', 'nobs', 'df'],
    digits = 4,
    **kwargs
  ):
  '''compare_ols() で出力する表の下部に追加する当てはまり指標の表を作成する関数'''
  # モデル名が指定されていない場合、連番を作成する
  if model_name is None:
      model_name = [f'model {i + 1}' for i in range(len(list_models))]

  glance_list = [glance(mod) for mod in list_models]

  # glance_list 内のデータフレームの列名の和集合を取得
  # つまり、代入されたどのモデルの、当てはまりの指標にもない名前を指定することはできないという処理
  union_set = glance_list[0].columns
  for i in range(1, len(glance_list)):
    union_set = union_set.union(glance_list[i].columns)

  # 引数に妥当な値が指定されているかを検証
  stats_glance = bild.arg_match(
              stats_glance,
              values = union_set.to_list(),
              arg_name = 'stats_glance',
              multiple = True
              )

  res = pd.concat(glance_list)\
    .loc[:, stats_glance]\
    .round(digits)\
    .apply(bild.pad_zero, digits = digits).T

  res.columns = model_name
  res[res == 'nan'] = ''
  res.index.name = 'term'
  return res


# In[ ]:


# 複数のモデルを比較する表を作成する関数 対象を sm.ols() に限定しないバージョン
def lineup_models(tidy_list, model_name = None, subset = None, **kwargs):

    # モデル名が指定されていない場合、連番を作成する
    if model_name is None:
        model_name = [f'model {i + 1}' for i in range(len(tidy_list))]

    # tidy_list の各要素に gazer() 関数を適用
    list_gazer = [gazer(df, **kwargs) for df in tidy_list]

    # model_name が列名になるように、辞書の key に設定してから pd.concat() で結合
    res = pd.concat(dict(zip(model_name, list_gazer)), axis = 'columns')\
        .droplevel(1, axis = 'columns') # 列名が2重に設定されるので、これを削除して1つにします。

    # subset が指定された場合は該当する変数を抽出します。
    if subset is not None:
        res = res.loc[subset, :]

    # モデルで使用されていない変数について NaN が発生するので、空白で置き換えます。
    res = res.fillna('')

    return res


# In[ ]:


# 回帰係数と検定統計量を縦に並べる関数
# 2024年1月30日変更 引数 stats と table_style について
# 妥当な値が指定されているかを検証する機能を追加しました。
# 2024年3月18日変更 数値の体裁を整える処理を bild.style_number() を使ったものに変更しました。
def gazer(
    res_tidy, estimate = 'estimate', stats = 'std_err',
    digits = 4, add_stars = True,  p_min = 0.01,
    table_style = 'two_line', line_break = '\n',
    **kwargs
    ):

    # 引数に妥当な値が指定されているかを検証
    stats = bild.arg_match(
        stats, ['std_err', 'statistics', 'p_value', 'conf_int'],
        arg_name = 'stats'
        )
    # こちらは部分一致可としています。
    table_style = bild.match_arg(
        table_style, ['two_line', 'one_line'],
        arg_name = 'table_style'
        )

    # --------------------
    res = res_tidy.copy()
    # 有意性を表すアスタリスクを作成します
    res['stars'] = ' ' + bild.p_stars(res['p_value'])

    # # `estimate` と `stats` を見やすいフォーマットに変換します。
    # res[[estimate, stats]] = res[[estimate, stats]]\
    #     .apply(bild.style_number, digits = digits)

    # table_style に応じて改行とアスタリスクを追加する

    if(table_style == 'two_line'):
        sep = line_break
        if add_stars:
            sep = res['stars'] + sep
        sufix = ''

    elif(table_style == 'one_line'):
        sep = ''
        if add_stars:
            sufix = res['stars']
        else:
            sufix = ''

    if(stats == 'conf_int'):
      res[[estimate, 'conf_lower', 'conf_higher']] \
        = res[[estimate, 'conf_lower', 'conf_higher']]\
          .apply(bild.style_number, digits = digits)

      res['value'] =  res[estimate] + sep\
       + '[' + res['conf_lower'] + ', ' + res['conf_higher'] + ']'\
       + sufix
    else:
      # `estimate` と `stats` を見やすいフォーマットに変換します。
      res[[estimate, stats]] = res[[estimate, stats]]\
        .apply(bild.style_number, digits = digits)
      res['value'] = res[estimate] + sep + '(' + res[stats] + ')' + sufix

    # モデルで使用されていない変数について NaN が発生するので、空白で置き換えます。
    res = res.fillna('')

    return res[['value']]


# ### `gazer()` 関数の多項ロジットモデルバージョン

# ## 回帰係数の視覚化関数
# 

# In[ ]:


# 利用するライブラリー
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
# import japanize_matplotlib #日本語化matplotlib
from statsmodels.iolib.summary import summary_params_frame

# 回帰分析の結果から回帰係数のグラフを作成する関数 --------
def coefplot(
    mod,
    subset = None,
    conf_level = [0.95, 0.99],
    palette = ['#1b69af', '#629CE7'],
    show_Intercept = False,
    show_vline = True,
    ax = None,
    **kwargs
    ):
    '''model object から回帰係数のグラフを作成する関数'''

    bild.assert_float(conf_level, lower = 0, upper = 1, inclusive = 'neither')
    bild.assert_character(palette)

    # 回帰係数の表を抽出
    tidy_ci_high = tidy(mod, conf_level = conf_level[0])
    tidy_ci_row = tidy(mod, conf_level = conf_level[1])

    # subset が指定されていれば、回帰係数の部分集合を抽出する
    if subset is not None:
        tidy_ci_high = tidy_ci_high.loc[subset, :]
        tidy_ci_row = tidy_ci_row.loc[subset, :]

    # グラフの作成
    coef_dot(
        tidy_ci_high, tidy_ci_row, palette = palette,
        show_Intercept = show_Intercept, show_vline = show_vline,
        ax = ax, **kwargs
        )


def coef_dot(
    tidy_ci_high, tidy_ci_low,
    ax = None,
    show_Intercept = False,
    show_vline = True,
    palette = ['#1b69af', '#629CE7'],
    estimate = 'estimate', conf_lower = 'conf_lower', conf_higher = 'conf_higher',
    ):
    '''tidy_talbe から回帰係数のグラフを作成する関数'''
    tidy_ci_high = tidy_ci_high.copy()
    tidy_ci_low = tidy_ci_low.copy()

    # 切片項を除外する
    if not show_Intercept:
        tidy_ci_high = tidy_ci_high.loc[~ tidy_ci_high.index.isin(['Intercept']), :]
        tidy_ci_low = tidy_ci_low.loc[~ tidy_ci_low.index.isin(['Intercept']), :]


    if ax is None:
        fig, ax = plt.subplots()

    # 図の描画 -----------------------------
    # 垂直線の描画
    if show_vline:
        ax.axvline(0, ls = "--", color = '#969696')

    # エラーバーの作図
    ax.hlines(
        y = tidy_ci_low.index, xmin = tidy_ci_low[conf_lower], xmax = tidy_ci_low[conf_higher],
        linewidth = 1.5,
        color = palette[1]
    )
    ax.hlines(
        y = tidy_ci_high.index, xmin = tidy_ci_high[conf_lower], xmax = tidy_ci_high[conf_higher],
        linewidth = 3,
        color = palette[0]
    )

    # 回帰係数の推定値を表す点の作図
    ax.scatter(
      x = tidy_ci_high[estimate],
      y = tidy_ci_high.index,
      c = palette[0],
      s = 60
    )
    ax.set_ylabel('');


# ## `reg.compare_mfx()`
# 

# In[ ]:


def tidy_mfx(
    x,
    at = 'overall',
    method = 'dydx',
    dummy = False,
    conf_level = 0.95,
    **kwargs):
  # 引数に妥当な値が指定されているかを検証
  bild.assert_float(conf_level, lower = 0, upper = 1, inclusive = 'neither')
  at = bild.arg_match(at, ['overall', 'mean', 'median', 'zero'], arg_name = 'at')

  method = bild.arg_match(
      method,
      values = ['coef', 'dydx', 'eyex', 'dyex', 'eydx'],
      arg_name = 'method'
      )
  # 限界効果の推定
  est_margeff = x.get_margeff(dummy = dummy, at = at, method = method, **kwargs)
  tab = est_margeff.summary_frame()

  method_dict = {
            'coef':'coef',
            'dydx':'dy/dx',
            'eyex':'d(lny)/d(lnx)',
            'dyex':'dy/d(lnx)',
            'eydx':'d(lny)/dx',
        }

  tab = tab.rename(columns = {
            method_dict[method]:'estimate',
            'Std. Err.':'std_err',
            'z':'statistics',
            'Pr(>|z|)':'p_value',
            'Conf. Int. Low':'conf_lower',
            'Cont. Int. Hi.':'conf_higher'
            })

  # conf_level に 0.95 以外の値が指定されていた場合は、信頼区間を個別に推定して値を書き換えます。
  if(conf_level != 0.95):
    CI = est_margeff.conf_int(alpha = 1 - conf_level)
    tab['conf_lower'] = CI[:, 0]
    tab['conf_higher'] = CI[:, 1]

  return tab


# In[ ]:


# 複数のロジットモデルを比較する表を作成する関数
def compare_mfx(
    list_models,
    model_name = None,
    subset = None,
    stats = 'std_err',
    add_stars = True,
    stats_glance = ['prsquared', 'nobs', 'df'],
    at = 'overall',
    method = 'dydx',
    dummy = False,
    digits = 4,
    table_style = 'two_line',
    line_break = '\n',
    **kwargs
    ):
  assert pandas.api.types.is_list_like(list_models), "argument 'list_models' is must be a list of models."
  assert_reg_reuslt(list_models)
  # 限界効果の推定-------------
  if method == 'coef':
      tidy_list = [tidy(mod) for mod in list_models]
  else:
      tidy_list = [
          tidy_mfx(mod, at = at, method = method, dummy = dummy)
          for mod in list_models
          ]

  # モデル名が指定されていない場合、連番を作成する
  if model_name is None:
      model_name = [f'model {i + 1}' for i in range(len(tidy_list))]

  # lineup_models() を適用してモデルを比較する表を作成
  res = lineup_models(
      tidy_list,
      model_name = model_name,
      digits = digits,
      subset = subset,
      stats = stats,
      add_stars = add_stars,
      table_style = table_style,
      estimate = 'estimate',
      line_break = line_break,
      **kwargs
      )

  res.index.name = 'term'
  # 表の下部にモデルの当てはまりに関する統計値を追加
  if stats_glance is not None: # もし stats_glance が None なら統計値を追加しない
      res2 = make_glance_tab(
          list_models,
          model_name = model_name,
          stats_glance = stats_glance,
          digits = digits
          )
      res = pd.concat([res, res2])

  return res


# In[ ]:


# 回帰分析の結果から回帰係数のグラフを作成する関数 --------
def mfxplot(
    mod,
    subset = None,
    conf_level = [0.95, 0.99],
    at = 'overall',
    method = 'dydx',
    dummy = False,
    palette = ['#1b69af', '#629CE7'],
    show_Intercept = False,
    show_vline = True,
    ax = None,
    **kwargs
    ):
    '''model object から回帰係数のグラフを作成する関数'''

    # 回帰係数の表を抽出
    tidy_ci_high = tidy_mfx(
        mod, at = at, method = method, dummy = dummy, conf_level = conf_level[0]
        )
    tidy_ci_row =  tidy_mfx(
        mod, at = at, method = method, dummy = dummy, conf_level = conf_level[1]
        )

    # subset が指定されていれば、回帰係数の部分集合を抽出する
    if subset is not None:
        tidy_ci_high = tidy_ci_high.loc[subset, :]
        tidy_ci_row = tidy_ci_row.loc[subset, :]

    # グラフの作成
    coef_dot(
        tidy_ci_high, tidy_ci_row, estimate = 'estimate', palette = palette,
        show_Intercept = show_Intercept, show_vline = show_vline,
        ax = ax, **kwargs
        )


# ### 多項ロジスティック回帰用

# In[ ]:


def gazer_MNlogit(MNlogit_margeff, endog_categories = None, **kwargs):

    if ~pd.Series(MNlogit_margeff.columns).isin(['endog']).any():
        MNlogit_margeff = MNlogit_margeff.reset_index(level = 'endog')

    if endog_categories is None:
        endog_categories = MNlogit_margeff['endog'].unique()

    # gazer 関数で扱えるように列名を修正します。
    MNlogit_margeff = MNlogit_margeff.rename(columns = {
            'Std. Err.':'std_err',
            'z':'statistics',
            'Pr(>|z|)':'p_value',
            'Conf. Int. Low':'conf_lower',
            'Cont. Int. Hi.':'conf_higher'
            }
    )

    list_gazer = list(map(
        lambda categ : gazer(
        MNlogit_margeff.query('endog == @categ'),
        estimate = 'dy/dx',
        **kwargs
        ),
        endog_categories
        ))

    endog_categories2 = [i.split('[')[1].split(']')[0] for i in endog_categories]

    # # flm_total.keys() で回帰式を作成したときに設定したモデル名を抽出し、列名にします。
    res = pd.concat(dict(zip(list(endog_categories2), list_gazer)), axis = 'columns')\
        .droplevel(1, axis = 'columns') # 列名が2重に設定されるので、これを削除して1つにします。

    return res

