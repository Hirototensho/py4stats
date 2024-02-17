# -*- coding: utf-8 -*-
"""eda_tools.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Y3xPJY-zCwrnVo5iOiuDKZwMgs2qvHhX

# `eda_tools`：回帰分析の結果を要約する関数群
"""

import argparse

def match_arg(value, choices):
    """
    Simulates the functionality of R's match.arg() function with partial matching in Python.

    Args:
    - value: The value to match against the choices (partially).
    - choices: List of valid choices.

    Returns:
    - The matched value if found in choices (partially), otherwise raises an ArgumentError.
    """
    matches = [c for c in choices if value.lower() in c.lower()]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise ValueError(f"Ambiguous value: '{value}'. Matches multiple choices: {', '.join(matches)}.")
    else:
        # raise ValueError(f"No match found for value: '{value}'.")
        raise argparse.ArgumentTypeError(f"Invalid choice: '{value}'. Should be one of: {', '.join(choices)}.")

"""## `diagnose()`

- `index`（行名）：もとのデータフレームの列名に対応しています。
- `dtype`：該当する列のpandasにおけるデータの型。「〇〇の個数」や「〇〇の金額」といった列の dtype が `object` になっていたら、文字列として読み込まれているので要注意です。

- `missing_count`：該当する列のなかで `NaN` などの欠測値になっている数
- `missing_percent`：該当する列のなかで欠測値が占めている割合で 欠`missing_percent = 100 * missing_count/ nrow` として計算されます。もし `missing_percent = 100` なら、その列は完全に空白です。
- `unique_count`：その列で重複を除外したユニークな値の数。例えばある列の中身が「a, a, b, b, b」であればユニークな値は `a` と `b` の2つなのでユニーク値の数は2です。もし ユニーク値の数 = 1 であれば、その行にはたった1種類の値しか含まれていないことが分かりますし、例えば都道府県を表す列のユニーク値の数が47より多ければ、都道府県以外のものが混ざっていると考えられます。
- `unique_rate`： サンプルに占めるユニークな値の割合。 `unique_rate = 100 * unique_count / nrow`と計算されます。 `unique_rate = 100` であれば、全ての行に異なる値が入っています。一般的に実数値の列はユニーク率が高くなりますが、年齢の「20代」や価格の「400円代」のように、階級に分けられている場合にはユニーク率が低くなります。
"""

import pandas as pd
import numpy as np
import scipy as sp
import pandas_flavor as pf

def missing_percent(x, axis = 'index', pct = True):
  return (100**pct) * x.isna().mean(axis = axis)

@pf.register_dataframe_method
def diagnose(self):
    # 各種集計値の計算
     result = self.agg([
         'dtype',
         lambda x: x.isna().sum(),                  # missing_count
         missing_percent,                           # missing_percent
         'nunique',                                 # unique_count
         lambda x: (x.nunique() / len(x) ) * 100    # unique_rate
         ]).T

     # 列名の修正
     result.columns = ['dtype', 'missing_count', 'missing_percent', 'unique_count', 'unique_rate']

     return result

"""## 完全な空白列 and / or 行の除去"""

@pf.register_dataframe_method
def remove_empty(self, cols = True, rows = True, cutoff = 1, quiet = True):
  df_shape = self.shape

  # 空白列の除去 ------------------------------
  if cols :
    empty_col = missing_percent(self, axis = 'index', pct = False) >= 1
    self = self.loc[:, ~empty_col]

    if not(quiet) :
      ncol_removed = empty_col.sum()
      col_removed = empty_col[empty_col].index.to_series().astype('str').to_list()
      print(
            f"Removing {ncol_removed} empty column(s) out of {df_shape[1]} columns" +
            f"(Removed: {','.join(col_removed)}). "
            )
  # 空白行の除去 ------------------------------
  if rows :
    empty_rows = missing_percent(self, axis = 'columns', pct = False) >= 1
    self = self.loc[~empty_rows, :]

    if not(quiet) :
        nrow_removed = empty_rows.sum()
        row_removed = empty_rows[empty_rows].index.to_series().astype('str').to_list()
        print(
              f"Removing {nrow_removed} empty row(s) out of {df_shape[0]} rows" +
              f"(Removed: {','.join(row_removed)}). "
          )

  return self

"""## 定数列の除去"""

@pf.register_dataframe_method
def remove_constant(self, quiet = True, dropna = False):
  df_shape = self.shape
  # データフレーム(self) の行が定数かどうかを判定
  constant_col = self.nunique(dropna = dropna) == 1
  self = self.loc[:, ~constant_col]

  if not(quiet) :
    ncol_removed = constant_col.sum()
    col_removed = constant_col[constant_col].index.to_series().astype('str').to_list()

    print(
        f"Removing {ncol_removed} constant column(s) out of {df_shape[1]} columns" +
        f"(Removed: {','.join(col_removed)}). "
     )


  return self

# 列名に特定の文字列を含む列を除外する関数
@pf.register_dataframe_method
def filtering_out(self, contains = None, starts_with = None, ends_with = None):
    if contains is not None:
      assert isinstance(contains, str), "'contains' must be a string."
      self = self.loc[:, self.apply(lambda x: contains not in x.name)]

    if starts_with is not None:
      assert isinstance(starts_with, str), "'starts_with' must be a string."
      self = self.loc[:, self.apply(lambda x: not x.name.startswith(starts_with))]

    if ends_with is not None:
      assert isinstance(ends_with, str), "'ends_with' must be a string."
      self = self.loc[:, self.apply(lambda x: not x.name.endswith(ends_with))]

    return self

"""## クロス集計表ほか"""

def crosstab2(
    data, index, columns, values=None, rownames=None, colnames=None,
    aggfunc=None, margins=False, margins_name='All', dropna=True, normalize=False
    ):

    res = pd.crosstab(
        index = data[index], columns = data[columns], values = values,
        rownames = rownames, colnames = colnames,
        aggfunc = aggfunc, margins = margins, margins_name = margins_name,
        dropna = dropna, normalize = normalize
        )
    return res

# -------------------------------
# def freq_table(data, x, sort = True, group = None, dropna = False):

#     if group is None:

#         count = data[x].value_counts(sort = sort, dropna = dropna)
#         rel_count = data[x].value_counts(sort = sort, normalize=True, dropna = dropna)

#     # sort = False の場合 index でソートします。
#         if (not sort):
#             count = count.sort_index()
#             rel_count = rel_count.sort_index()

#         res = pd.DataFrame({
#             'freq':count,
#             'perc':rel_count,
#             'cumfreq':count.cumsum(),
#             'cumperc':rel_count.cumsum()
#         })
#     else:
#         res = pd.crosstab(data[x], data[group]).reset_index()\
#             .melt(id_vars = x, value_vars = data[group].dropna().unique())\
#             .sort_values([group, x]).set_index([group, x])

#         res = res.rename(columns = {'value':'freq'})

#         if sort: res = res.sort_values([group, 'freq'], ascending = [True, False])

#         res['total'] = res.groupby(group).transform('sum')
#         res['perc'] = res['freq'] / res['total']
#         res['cumfreq'] = res.groupby(group)['freq'].cumsum()
#         res['cumperc'] = res.groupby(group)['perc'].cumsum()
#         res = res.drop('total', axis = 'columns')

#     return res

@pf.register_dataframe_method
def freq_table(self, colum, group = None, sort = True, dropna = False):
    # group が指定されていない場合の処理
    if group is None:
        count = self[colum].value_counts(sort = sort, dropna = dropna)
        rel_count = self[colum].value_counts(sort = sort, normalize=True, dropna = dropna)

    # sort = False の場合 index でソートします。
        if (not sort):
            count = count.sort_index()
            rel_count = rel_count.sort_index()

        res = pd.DataFrame({
            'freq':count,
            'perc':rel_count,
            'cumfreq':count.cumsum(),
            'cumperc':rel_count.cumsum()
        })
        res.index.name = colum
      # group が指定された場合の処理
    else:
        res = pd.crosstab(self[colum], self[group]).reset_index()\
            .melt(id_vars = colum, value_vars = self[group].dropna().unique())\
            .sort_values([group, colum]).set_index([group, colum])

        res = res.rename(columns = {'value':'freq'})

        if sort: res = res.sort_values([group, 'freq'], ascending = [True, False])

        res['total'] = res.groupby(group).transform('sum')
        res['perc'] = res['freq'] / res['total']
        res['cumfreq'] = res.groupby(group)['freq'].cumsum()
        res['cumperc'] = res.groupby(group)['perc'].cumsum()
        res = res.drop('total', axis = 'columns')

    return res

def pad_z(s, digits):
    s_digits = len(s[s.find('.'):])
    s = s + '0'*(digits + 1 - s_digits)
    return s

pad_zero = np.vectorize(pad_z, excluded = 'digits')

def add_big_mark(s): return  f'{s:,}'

# def tabyl(
#     data, index, columns, values=None, rownames=None, colnames=None,
#     aggfunc=None, margins=True, margins_name='All', dropna = False, normalize='index',
#     digits = 1
#     ):

#     if data[index].dtype == "bool":
#         data[index] = data[index].astype(str)
#     if data[columns].dtype == "bool":
#         data[columns] = data[columns].astype(str)

#     # 度数クロス集計表（最終的な表では左側の数字）
#     c_tab1 = pd.crosstab(
#         index = data[index], columns = data[columns], values = values,
#         rownames = rownames, colnames = colnames,
#         aggfunc = aggfunc, margins = margins, margins_name = margins_name,
#         dropna = dropna, normalize = False
#         )

#     # c_tab1 = c_tab1.style.format('{:,d}')

#     c_tab1 = c_tab1.applymap(add_big_mark)

#     # 回答率クロス集計表（最終的な表では括弧内の数字）
#     c_tab2 = pd.crosstab(
#         index = data[index], columns = data[columns], values = values,
#         rownames = rownames, colnames = colnames,
#         aggfunc = aggfunc, margins = margins, margins_name = margins_name,
#         dropna = dropna, normalize = normalize
#         )

#     # 2つめのクロス集計表の回答率をdigitsで指定した桁数のパーセントに換算し、文字列化します。
#     c_tab2 = (100 * c_tab2).round(digits).astype('str').apply(pad_zero, digits = digits)

#     col = c_tab2.columns
#     idx = c_tab2.index
#     # 1つめのクロス集計表も文字列化して、↑で計算したパーセントに丸括弧と%記号を追加したものを文字列として結合します。
#     c_tab1.loc[idx, col] = c_tab1.astype('str').loc[idx, col] + ' (' + c_tab2 + '%)'
#     # c_tab1.loc[idx, col] = c_tab1.astype('str').loc[idx, col] + f'({c_tab2}%)'

#     return c_tab1

@pf.register_dataframe_method
def tabyl(
    self, index, columns, values=None, rownames=None, colnames=None,
    aggfunc=None, margins=True, margins_name='All', dropna = False, normalize='index',
    digits = 1
    ):

    if(not isinstance(normalize, bool)):
      normalize = match_arg(normalize, ['index', 'columns', 'all'])

    if self[index].dtype == "bool":
        self[index] = self[index].astype(str)
    if self[columns].dtype == "bool":
        self[columns] = self[columns].astype(str)

    # 度数クロス集計表（最終的な表では左側の数字）
    c_tab1 = pd.crosstab(
        index = self[index], columns = self[columns], values = values,
        rownames = rownames, colnames = colnames,
        aggfunc = aggfunc, margins = margins, margins_name = margins_name,
        dropna = dropna, normalize = False
        )

    c_tab1 = c_tab1.applymap(add_big_mark)

    if(normalize != False):

      # 回答率クロス集計表（最終的な表では括弧内の数字）
      c_tab2 = pd.crosstab(
          index = self[index], columns = self[columns], values = values,
          rownames = rownames, colnames = colnames,
          aggfunc = aggfunc, margins = margins, margins_name = margins_name,
          dropna = dropna, normalize = normalize
          )

      # 2つめのクロス集計表の回答率をdigitsで指定した桁数のパーセントに換算し、文字列化します。
      c_tab2 = (100 * c_tab2).round(digits).astype('str').apply(pad_zero, digits = digits)

      col = c_tab2.columns
      idx = c_tab2.index
      # 1つめのクロス集計表も文字列化して、↑で計算したパーセントに丸括弧と%記号を追加したものを文字列として結合します。
      c_tab1.loc[idx, col] = c_tab1.astype('str').loc[idx, col] + ' (' + c_tab2 + '%)'

    return c_tab1

"""## `diagnose_category()`：カテゴリー変数専用の要約関数"""

# 適切なダミー変数かどうかを判定する関数
def is_dummy(x): return x.isin([0, 1]).all(axis = 'index')

# カテゴリカル変数についての集計関数 --------------

# 情報エントロピーと、その値を0から1に標準化したもの --------------
def entropy(X, base = 2, axis = 0):
    vc = pd.Series(X).value_counts(normalize = True, sort = False)
    res = sp.stats.entropy(pk = vc,  base = base, axis = axis)
    return res

def std_entropy(X, axis = 0):
    K = pd.Series(X).nunique()
    res = entropy(X, base = K) if K > 1 else 0.0
    return res

def freq_mode(x, normalize = False):
    res = x.value_counts(normalize = normalize, dropna = False).iloc[0]
    return res

# カテゴリカル変数についての概要を示す関数
def diagnose_category(data):
    # 01のダミー変数はロジカル変数に変換
    data = data.copy()
    data.loc[:, is_dummy(data)] = (data.loc[:, is_dummy(data)] == 1)
    # 文字列 or カテゴリー変数のみ抽出
    data = data.select_dtypes(include = [object, 'category', bool])

    n = len(data)
    # describe で集計表の大まかな形を作成
    res = data.describe().T
    res['freq'] = res['freq'].astype('int')
    # 追加の集計値を計算して代入
    res = res.assign(
        unique_percent = 100 * data.nunique(dropna = False) / n,
        missing_percent = missing_percent(data),
        pct_mode = (100 * (res['freq'] / n)),
        std_entropy = data.agg(std_entropy)
    )
    # 見やすいように並べ替え
    res = res.loc[:, [
        'count', 'missing_percent', 'unique', 'unique_percent',
        'top', 'freq', 'pct_mode', 'std_entropy'
        ]]

    return res

"""## その他の補助関数"""

def weighted_mean(x, w):
  wmean = (x * w).sum() / w.sum()
  return wmean

def scale(x, ddof = 1):
    z = (x - x.mean()) / x.std(ddof = ddof)
    return z

def min_max(x):
  mn = (x - x.min()) / (x.max() - x.min())
  return mn

"""# パレート図を作図する関数"""

import matplotlib.pyplot as plt

# パレート図に使用するランキングを作成する関数
def make_rank_table(data, group, values, aggfunc = 'sum'):
    # ピボットテーブルを使って、カテゴリー group（例：メーカー）ごとの values （例：販売額）の合計を計算
    p_table = pd.pivot_table(
        data = data,
        index = group,
        values = values,
        aggfunc = aggfunc,
        fill_value = 0
        )
    # values の値に基づいてソート
    rank_table = p_table.sort_values(values, ascending=False)

    # シェア率と累積相対度数を計算
    rank_table['share'] = (rank_table[values] / rank_table[values].sum())
    rank_table['cumshare'] = rank_table['share'].cumsum()
    return rank_table
    # return p_table

# -----------------------------------------------
# パレート図を作成する関数
def Pareto_plot(
    data, group, values = None, top_n = 20, aggfunc = 'sum',
    ax = None, fontsize = 12, palette = {'bar':'#478FCE', 'line':'#252525'},
    xlab_rotation = 90
    ):

    # 指定された変数でのランクを表すデータフレームを作成
    # グラフの見やすさのために上位 top_n 件を抽出します。
    if values is None:
        shere_rank = freq_table(data, group, dropna = True).head(top_n)
        cumlative = 'cumfreq'
    else:
        shere_rank = make_rank_table(data, group, values, aggfunc = aggfunc).head(top_n)
        cumlative = 'cumshare'


    # グラフの描画
    if ax is None:
        fig, ax = plt.subplots()

    # yで指定された変数の棒グラフ

    # グラフの見やすさのために上位 top_n 件を抽出します。
    if values is None:
        ax.bar(shere_rank.index, shere_rank['freq'], color = palette['bar'])
        ax.set_ylabel('freq', fontsize = fontsize * 1.1)
    else:
        # yで指定された変数の棒グラフ
        ax.bar(shere_rank.index, shere_rank[values], color = palette['bar'])
        ax.set_ylabel(values, fontsize = fontsize * 1.1)


    ax.set_xlabel(group, fontsize = fontsize * 1.1)

    # 累積相対度数の線グラフ
    ax2 = ax.twinx()
    ax2.plot(
        shere_rank.index, shere_rank[cumlative],
        linestyle = 'dashed', color = palette['line'], marker = 'o'
        )

    ax2.set_xlabel(group, fontsize = fontsize * 1.1)
    ax2.set_ylabel(cumlative, fontsize = fontsize * 1.1)

    # x軸メモリの回転
    ax.xaxis.set_tick_params(rotation = xlab_rotation, labelsize = fontsize)
    ax2.xaxis.set_tick_params(rotation = xlab_rotation, labelsize = fontsize);
    ax.yaxis.set_tick_params(labelsize = fontsize * 0.9)
    ax2.yaxis.set_tick_params(labelsize = fontsize * 0.9);

