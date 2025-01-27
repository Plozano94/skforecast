################################################################################
#                        skforecast.model_selection                            #
#                                                                              #
# This work by Joaquín Amat Rodrigo is licensed under a Creative Commons       #
# Attribution 4.0 International License.                                       #
################################################################################
# coding=utf-8


import typing
from typing import Union, Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import logging
import tqdm
from sklearn.metrics import mean_squared_error 
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import ParameterGrid

from .ForecasterAutoreg import ForecasterAutoreg
from .ForecasterAutoregCustom import ForecasterAutoregCustom
from .ForecasterAutoregMultiOutput import ForecasterAutoregMultiOutput

logging.basicConfig(
    format = '%(name)-10s %(levelname)-5s %(message)s', 
    level  = logging.INFO,
)


def time_series_spliter(y: Union[np.ndarray, pd.Series],
                        initial_train_size: int, steps: int,
                        allow_incomplete_fold: bool=True,
                        verbose: bool=True):
    '''
    
    Split indices of a time series into multiple train-test pairs. The order of
    is maintained and the training set increases in each iteration.
    
    Parameters
    ----------        
    y : 1D np.ndarray, pd.Series
        Training time series values. 
    
    initial_train_size: int 
        Number of samples in the initial train split.
        
    steps : int
        Number of steps to predict.
        
    allow_incomplete_fold : bool, default `True`
        The last test set is allowed to be incomplete if it does not reach `steps`
        observations. Otherwise, the latest observations are discarded.
        
    verbose : bool, default `True`
        Print number of splits created.

    Yields
    ------
    train : 1D np.ndarray
        Training indices.
        
    test : 1D np.ndarray
        Test indices.
        
    '''
    
    if not isinstance(y, (np.ndarray, pd.Series)):

        raise Exception('`y` must be `1D np.ndarray` o `pd.Series`.')

    elif isinstance(y, np.ndarray) and y.ndim != 1:

        raise Exception(
            f"`y` must be `1D np.ndarray` o `pd.Series`, "
            f"got `np.ndarray` with {y.ndim} dimensions."
        )
        
    if initial_train_size > len(y):
        raise Exception(
            '`initial_train_size` must be smaller than lenght of `y`.'
            ' Try to reduce `initial_train_size` or `steps`.'
        )

    if isinstance(y, pd.Series):
        y = y.to_numpy().copy()
    
  
    folds = (len(y) - initial_train_size) // steps  + 1
    # +1 fold is needed to allow including the remainder in the last iteration.
    remainder = (len(y) - initial_train_size) % steps   
    
    if verbose:
        if folds == 1:
            print(f"Number of folds: {folds - 1}")
            print("Not enought observations in `y` to create even a complete fold."
                  " Try to reduce `initial_train_size` or `steps`."
            )

        elif remainder == 0:
            print(f"Number of folds: {folds - 1}")

        elif remainder != 0 and allow_incomplete_fold:
            print(f"Number of folds: {folds}")
            print(
                f"Since `allow_incomplete_fold=True`, "
                f"last fold only includes {remainder} observations instead of {steps}."
            )
            print(
                'Incomplete folds with few observations could overestimate or ',
                'underestimate validation metrics.'
            )
        elif remainder != 0 and not allow_incomplete_fold:
            print(f"Number of folds: {folds - 1}")
            print(
                f"Since `allow_incomplete_fold=False`, "
                f"last {remainder} observations are descarted."
            )

    if folds == 1:
        # There are no observations to create even a complete fold
        return []
    
    for i in range(folds):
          
        if i < folds - 1:
            train_end     = initial_train_size + i * steps    
            train_indices = range(train_end)
            test_indices  = range(train_end, train_end + steps)
            
        else:
            if remainder != 0 and allow_incomplete_fold:
                train_end     = initial_train_size + i * steps  
                train_indices = range(train_end)
                test_indices  = range(train_end, len(y))
            else:
                break
        
        yield train_indices, test_indices
        
        
def get_metric(metric:str) -> callable:
    '''
    Get the corresponding scikitlearn function to calculate the metric.
    
    Parameters
    ----------
    metric : {'mean_squared_error', 'mean_absolute_error', 'mean_absolute_percentage_error'}
        Metric used to quantify the goodness of fit of the model.
    
    Returns 
    -------
    metric : callable
        scikitlearn function to calculate the desired metric.
    '''
    
    if metric not in ['mean_squared_error', 'mean_absolute_error',
                      'mean_absolute_percentage_error']:
        raise Exception(
            f"Allowed metrics are: 'mean_squared_error', 'mean_absolute_error' and "
            f"'mean_absolute_percentage_error'. Got {metric}."
        )
    
    metrics = {
        'mean_squared_error': mean_squared_error,
        'mean_absolute_error': mean_absolute_error,
        'mean_absolute_percentage_error': mean_absolute_percentage_error
    }
    
    metric = metrics[metric]
    
    return metric
    

def cv_forecaster(forecaster, y: Union[np.ndarray, pd.Series],
                  initial_train_size: int, steps: Union[int, None], metric: str,
                  exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None,
                  allow_incomplete_fold: bool=True, set_out_sample_residuals: bool=True,
                  verbose: bool=True) -> Tuple[np.array, np.array]:
    '''
    Cross-validation of `ForecasterAutoreg`, `ForecasterAutoregCustom`
    or `ForecasterAutoregMultiOutput` object. The order of data is maintained
    and the training set increases in each iteration.
    
    Parameters
    ----------
    forecaster : ForecasterAutoreg, ForecasterAutoregCustom, ForecasterAutoregMultiOutput
        `ForecasterAutoreg`, `ForecasterAutoregCustom` or `ForecasterAutoregMultiOutput` object.
        
    y : 1D np.ndarray, pd.Series
        Training time series values. 
    
    initial_train_size: int 
        Number of samples in the initial train split.
        
    steps : int, None
        Number of steps to predict. Ignored if `forecaster` is a `ForecasterAutoregMultiOutput`
        since this information is already stored inside it.
        
    metric : {'mean_squared_error', 'mean_absolute_error', 'mean_absolute_percentage_error'}
        Metric used to quantify the goodness of fit of the model.
        
    exog : np.ndarray, pd.Series, pd.DataFrame, default `None`
        Exogenous variable/s included as predictor/s. Must have the same
        number of observations as `y` and should be aligned so that y[i] is
        regressed on exog[i].
            
    allow_incomplete_fold : bool, default `True`
        The last test partition is allowed to be incomplete if it does not reach `steps`
        observations. Otherwise, the latest observations are discarded. This is set
        automatically set to `False` when forecaster is `ForecasterAutoregMultiOutput`.
    
    set_out_sample_residuals: bool, default `True`
        Save residuals generated during the cross-validation process as out of sample
        residuals.
        
    verbose : bool, default `True`
        Print number of folds used for cross validation.

    Returns 
    -------
    cv_metrics: 1D np.ndarray
        Value of the metric for each fold.

    cv_predictions: 1D np.ndarray
        Predictions.

    '''
    
    forecaster._check_y(y=y)
    y = forecaster._preproces_y(y=y)
    
    if exog is not None:
        forecaster._check_exog(exog=exog)
        exog = forecaster._preproces_exog(exog=exog)

    if initial_train_size > len(y):
        raise Exception(
            '`initial_train_size` must be smaller than lenght of `y`.'
        )
        
    if initial_train_size is not None and initial_train_size < forecaster.window_size:
        raise Exception(
            f"`initial_train_size` must be greater than "
            f"forecaster's window_size ({forecaster.window_size})."
        )  
    
    if isinstance(forecaster, ForecasterAutoregMultiOutput):
        steps = forecaster.steps
        if allow_incomplete_fold:
            logging.warning(
                " Cross-validation of `ForecasterAutoregMultiOutput` only allow completed folds, "
                 "`allow_incomplete_fold` is set to `False`."
            )
            allow_incomplete_fold = False
        
    metric = get_metric(metric=metric)
    
    splits = time_series_spliter(
                y                     = y,
                initial_train_size    = initial_train_size,
                steps                 = steps,
                allow_incomplete_fold = allow_incomplete_fold,
                verbose               = verbose
             )

    cv_predictions = []
    cv_metrics = []
    
    for train_index, test_index in splits:
        
        if exog is None:
            forecaster.fit(y=y[train_index])      
            pred = forecaster.predict(steps=len(test_index))
            
        else:
            
            forecaster.fit(y=y[train_index], exog=exog[train_index])      
            pred = forecaster.predict(steps=len(test_index), exog=exog[test_index])
               
        metric_value = metric(
                            y_true = y[test_index],
                            y_pred = pred
                       )
        
        cv_predictions.append(pred)
        cv_metrics.append(metric_value)
        
        if set_out_sample_residuals:
            if not isinstance(forecaster, ForecasterAutoregMultiOutput):
                forecaster.set_out_sample_residuals(y[test_index] - pred)
    
    if cv_predictions and cv_metrics:
        cv_predictions = np.concatenate(cv_predictions)
        cv_metrics = np.array(cv_metrics)
    else:
        cv_predictions = np.array([])
        cv_metrics = np.array([])
        
    return cv_metrics, cv_predictions


def backtesting_forecaster(forecaster, y: Union[np.ndarray, pd.Series],
                           steps: Union[int, None], metric: str, initial_train_size: None,
                           exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None,
                           set_out_sample_residuals: bool=True,
                           verbose: bool=False) -> Tuple[np.array, np.array]:
    '''
    Backtesting (validation) of `ForecasterAutoreg`, `ForecasterAutoregCustom` or
    `ForecasterAutoregMultiOutput` object.
    The model is trained only once using the `initial_train_size` first observations.
    In each iteration, a number of `steps` predictions are evaluated.   
    This evaluation is much faster than `cv_forecaster()` since the model is
    trained only once.

    If `forecaster` is already trained and `initial_train_size` is `None`,
    no initial train is done and all data is used to evaluate the model.
    However, the first `len(forecaster.last_window)` observations are needed
    to create the initial predictors, therefore, no predictions are
    calculated for them.
    
    Parameters
    ----------
    forecaster : ForecasterAutoreg, ForecasterAutoregCustom, ForecasterAutoregMultiOutput
        `ForecasterAutoreg`, `ForecasterAutoregCustom` or `ForecasterAutoregMultiOutput` object.
        
    y : 1D np.ndarray, pd.Series
        Training time series values. 
    
    initial_train_size: int, default `None`
        Number of samples in the initial train split. If `None` and `forecaster`
        is already trained, no initial train is done and all data is used to
        evaluate the model. However, the first `len(forecaster.last_window)`
        observations are needed to create the initial predictors. Therefore,
        no predictions are calculated for them.
        
    steps : int, None
        Number of steps to predict. Ignored if `forecaster` is a `ForecasterAutoregMultiOutput`
        since this information is already stored inside it.
        
    metric : {'mean_squared_error', 'mean_absolute_error', 'mean_absolute_percentage_error'}
        Metric used to quantify the goodness of fit of the model.
        
    exog : np.ndarray, pd.Series, pd.DataFrame, default `None`
        Exogenous variable/s included as predictor/s. Must have the same
        number of observations as `y` and should be aligned so that y[i] is
        regressed on exog[i].
        
    set_out_sample_residuals: bool, default `True`
        Save residuals generated during the cross-validation process as out of sample
        residuals.
            
    verbose : bool, default `False`
        Print number of folds used for backtesting.

    Returns 
    -------
    metric_value: np.ndarray shape (1,)
        Value of the metric.

    backtest_predictions: 1D np.ndarray
        Value of predictions.

    '''
    
    forecaster._check_y(y=y)
    y = forecaster._preproces_y(y=y)
    
    if exog is not None:
        forecaster._check_exog(exog=exog)
        exog = forecaster._preproces_exog(exog=exog)

    if initial_train_size is not None and initial_train_size > len(y):
        raise Exception(
            'If used, `initial_train_size` must be smaller than lenght of `y`.'
        )
        
    if initial_train_size is not None and initial_train_size < forecaster.window_size:
        raise Exception(
            f"`initial_train_size` must be greater than "
            f"forecaster's window_size ({forecaster.window_size})."
        )

    if initial_train_size is None and not forecaster.fitted:
        raise Exception(
            '`forecaster` must be already trained if no `initial_train_size` is provided.'
        )

    if initial_train_size is None and forecaster.fitted:
        logging.warning(
            f'Altough no initial train is done, the first '
            f'{len(forecaster.last_window)} observations are needed to create '
            f'the initial predictors. Therefore, no predictions are calculated for them.'
        )
    
    if isinstance(forecaster, ForecasterAutoregMultiOutput):
        steps = forecaster.steps
        
    metric = get_metric(metric=metric)
    backtest_predictions = []

    if initial_train_size is not None:
        if exog is None:
            forecaster.fit(y=y[:initial_train_size])      
        else:
            forecaster.fit(y=y[:initial_train_size], exog=exog[:initial_train_size])
        window_size = forecaster.window_size
    else:
        # Although not used for training, first observations are needed to create the initial predictors
        window_size = forecaster.window_size
        initial_train_size = window_size
    
    folds     = (len(y) - initial_train_size) // steps + 1
    remainder = (len(y) - initial_train_size) % steps
    
    if verbose:
        print(f"Number of observations used for training or as initial window: {initial_train_size}")
        print(f"Number of observations used for backtesting: {len(y) - initial_train_size}")
        print(f"    Number of folds: {folds - 1 * (remainder == 0)}")
        print(f"    Number of steps per fold: {steps}")
        if remainder != 0:
            print(f"    Last fold only includes {remainder} observations")
      
    for i in range(folds):
        last_window_end   = initial_train_size + i * steps
        last_window_start = (initial_train_size + i * steps) - window_size 
        last_window_y     = y[last_window_start:last_window_end]

        if exog is not None:
            next_window_exog    = exog[last_window_end:last_window_end + steps]
                
        if i < folds - 1:
            if exog is None:
                pred = forecaster.predict(
                            steps       = steps,
                            last_window = last_window_y
                        )
            else:
                pred = forecaster.predict(
                            steps       = steps,
                            last_window = last_window_y,
                            exog        = next_window_exog
                        )
                
        elif remainder != 0 and not isinstance(forecaster, ForecasterAutoregMultiOutput):
            steps = remainder 
            if exog is None:
                pred = forecaster.predict(
                            steps       = steps,
                            last_window = last_window_y
                        )
            else:
                pred = forecaster.predict(
                            steps       = steps,
                            last_window = last_window_y,
                            exog        = next_window_exog
                        )
                
        elif remainder != 0:
            # ForecasterAutoregMultiOutput predict all steps simultaneusly, therefore,
            # if the last fold is incomplete, remaining steps must be completed with
            # dummy values and removing then the corresponding predictions.
            dummy_steps = steps - remainder 
            if exog is None:
                pred = forecaster.predict(
                            steps       = steps,
                            last_window = last_window_y
                        )
                pred = pred[:-dummy_steps]
            else:
                next_window_exog = np.vstack((
                                     exog,
                                     np.ones(shape=(dummy_steps,) + exog.shape[1:])
                                   ))
                pred = forecaster.predict(
                            steps       = steps,
                            last_window = last_window_y,
                            exog        = next_window_exog
                        )
                pred = pred[:-dummy_steps]
            
        else:
            continue
        
        backtest_predictions.append(pred)
    
    backtest_predictions = np.concatenate(backtest_predictions)
    metric_value = metric(
                        y_true = y[initial_train_size: initial_train_size + len(backtest_predictions)],
                        y_pred = backtest_predictions
                   )
    
    if set_out_sample_residuals:
        if not isinstance(forecaster, ForecasterAutoregMultiOutput):
            forecaster.set_out_sample_residuals(
                y[initial_train_size: initial_train_size + len(backtest_predictions)] - backtest_predictions
            )

    return np.array([metric_value]), backtest_predictions



def grid_search_forecaster(forecaster, y: Union[np.ndarray, pd.Series],
                           param_grid: dict, initial_train_size: int, steps: int,
                           metric: str,
                           exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None,
                           lags_grid: list=None, method: str='cv',
                           allow_incomplete_fold: bool=True, return_best: bool=True,
                           verbose: bool=True) -> pd.DataFrame:
    '''
    Exhaustive search over specified parameter values for a Forecaster object.
    Validation is done using time series cross-validation or backtesting.
    
    Parameters
    ----------
    forecaster : ForecasterAutoreg, ForecasterAutoregCustom, ForecasterAutoregMultiOutput
        `ForecasterAutoreg`, `ForecasterAutoregCustom` or `ForecasterAutoregMultiOutput` object.
        
    y : 1D np.ndarray, pd.Series
        Training time series values. 
        
    param_grid : dict
        Dictionary with parameters names (`str`) as keys and lists of parameter
        settings to try as values.
    
    initial_train_size: int 
        Number of samples in the initial train split.
        
    steps : int
        Number of steps to predict.
        
    metric : {'mean_squared_error', 'mean_absolute_error', 'mean_absolute_percentage_error'}
        Metric used to quantify the goodness of fit of the model.
        
    exog : np.ndarray, pd.Series, pd.DataFrame, default `None`
        Exogenous variable/s included as predictor/s. Must have the same
        number of observations as `y` and should be aligned so that y[i] is
        regressed on exog[i].
           
    lags_grid : list of int, lists, np.narray or range. 
        Lists of `lags` to try. Only used if forecaster is an instance of 
        `ForecasterAutoreg`.
        
    method : {'cv', 'backtesting'}
        Method used to estimate the metric for each parameter combination.
        'cv' for time series crosvalidation and 'backtesting' for simple
        backtesting. 'backtesting' is much faster since the model is fitted only
        once.
        
    allow_incomplete_fold : bool, default `True`
        The last test set is allowed to be incomplete if it does not reach `steps`
        observations. Otherwise, the latest observations are discarded.
        
    return_best : bool
        Refit the `forecaster` using the best found parameters on the whole data.
        
    verbose : bool, default `True`
        Print number of folds used for cv or backtesting.

    Returns 
    -------
    results: pandas.DataFrame
        Metric value estimated for each combination of parameters.

    '''
    
    forecaster._check_y(y=y)
    y = forecaster._preproces_y(y=y)
    
    if exog is not None:
        forecaster._check_exog(exog=exog)
        exog = forecaster._preproces_exog(exog=exog)
    
    if isinstance(forecaster, ForecasterAutoregCustom):
        if lags_grid is not None:
            logging.warning(
                '`lags_grid` ignored if forecaster is an instance of `ForecasterAutoregCustom`.'
            )
        lags_grid = ['custom predictors']
        
    elif lags_grid is None:
        lags_grid = [forecaster.lags]
        
      
    lags_list = []
    params_list = []
    metric_list = []
    
    param_grid =  list(ParameterGrid(param_grid))

    logging.info(
        f"Number of models compared: {len(param_grid)*len(lags_grid)}"
    )
    
    for lags in tqdm.tqdm(lags_grid, desc='loop lags_grid', position=0):
        
        if isinstance(forecaster, (ForecasterAutoreg, ForecasterAutoregMultiOutput)):
            forecaster.set_lags(lags)
            lags = forecaster.lags.copy()
        
        for params in tqdm.tqdm(param_grid, desc='loop param_grid', position=1, leave=False):

            forecaster.set_params(**params)
            
            if method == 'cv':
                metrics = cv_forecaster(
                                forecaster               = forecaster,
                                y                        = y,
                                exog                     = exog,
                                initial_train_size       = initial_train_size,
                                steps                    = steps,
                                metric                   = metric,
                                allow_incomplete_fold    = allow_incomplete_fold,
                                set_out_sample_residuals = False,
                                verbose                  = verbose
                             )[0]
            else:
                metrics = backtesting_forecaster(
                                forecaster               = forecaster,
                                y                        = y,
                                exog                     = exog,
                                initial_train_size       = initial_train_size,
                                steps                    = steps,
                                metric                   = metric,
                                set_out_sample_residuals = False,
                                verbose                  = verbose
                             )[0]

            lags_list.append(lags)
            params_list.append(params)
            metric_list.append(metrics.mean())
            
    results = pd.DataFrame({
                'lags'  : lags_list,
                'params': params_list,
                'metric': metric_list})
    
    results = results.sort_values(by='metric', ascending=True)
    results = pd.concat([results, results['params'].apply(pd.Series)], axis=1)
    
    if return_best:
        
        best_lags = results['lags'].iloc[0]
        best_params = results['params'].iloc[0]
        logging.info(
            f"Refitting `forecaster` using the best found parameters and the whole data set: \n"
            f"lags: {best_lags} \n"
            f"params: {best_params}\n"
        )
        
        if isinstance(forecaster, (ForecasterAutoreg, ForecasterAutoregMultiOutput)):
            forecaster.set_lags(best_lags)
                
        forecaster.set_params(**best_params)
        forecaster.fit(y=y, exog=exog)
            
    return results


def backtesting_forecaster_intervals(
                           forecaster, y: Union[np.ndarray, pd.Series],
                           steps: int, metric: str, initial_train_size: int,
                           exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None,
                           interval: list=[5, 95], n_boot: int=500,
                           in_sample_residuals: bool=True, set_out_sample_residuals: bool=True,
                           verbose: bool=False) -> Tuple[np.array, np.array]:
    '''
    Backtesting (validation) of `ForecasterAutoreg`, or `ForecasterAutoregCustom` object.
    The model is trained only once using the `initial_train_size` first observations. In 
    each iteration, a number of `steps` predictions are evaluated. Both, predictions and
    intervals, are calculated. This evaluation is much faster than `cv_forecaster()` 
    since the model is trained only once.
    
    If `forecaster` is already trained and `initial_train_size` is `None`,
    no initial train is done and all data is used to evaluate the model.
    However, the first `len(forecaster.last_window)` observations are needed
    to create the initial predictors, therefore, no predictions are
    calculated for them.
    
    Parameters
    ----------
    forecaster : ForecasterAutoreg, ForecasterAutoregCustom
        `ForecasterAutoreg` or `ForecasterAutoregCustom` object.
        
    y : 1D np.ndarray, pd.Series
        Training time series values. 
    
    initial_train_size: int, default `None`
        Number of samples in the initial train split. If `None` and `forecaster`
        is already trained, no initial train is done and all data is used to
        evaluate the model. However, the first `len(forecaster.last_window)`
        observations are needed to create the initial predictors. Therefore,
        no predictions are calculated for them.
        
    steps : int
        Number of steps to predict.
        
    metric : {'mean_squared_error', 'mean_absolute_error', 'mean_absolute_percentage_error'}
        Metric used to quantify the goodness of fit of the model.
        
    exog : np.ndarray, pd.Series, pd.DataFrame, default `None`
        Exogenous variable/s included as predictor/s. Must have the same
        number of observations as `y` and should be aligned so that y[i] is
        regressed on exog[i].
        
    interval: list, default `[5, 100]`
            Confidence of the prediction interval estimated. Sequence of percentiles
            to compute, which must be between 0 and 100 inclusive.
            
    n_boot: int, default `500`
        Number of bootstrapping iterations used to estimate prediction
        intervals.

    in_sample_residuals: bool, default `True`
        If `True`, residuals from the training data are used as proxy of
        prediction error to create prediction intervals.
        
    set_out_sample_residuals: bool, default `True`
        Save residuals generated during the cross-validation process as out of sample
        residuals.
        
    verbose : bool, default `True`
        Print number of folds used for backtesting.

    Returns 
    -------
    backtest_predictions: np.ndarray
        2D np.ndarray shape(steps, 3) with predicted value and their estimated interval.
            Column 0 = predictions
            Column 1 = lower bound interval
            Column 2 = upper bound interval
        
    metric_value: np.ndarray shape (1,)
        Value of the metric.

    Notes
    -----
    More information about prediction intervals in forecasting:
    https://otexts.com/fpp2/prediction-intervals.html
    Forecasting: Principles and Practice (2nd ed) Rob J Hyndman and
    George Athanasopoulos.

    '''
    
    forecaster._check_y(y=y)
    y = forecaster._preproces_y(y=y)
    
    if exog is not None:
        forecaster._check_exog(exog=exog)
        exog = forecaster._preproces_exog(exog=exog)

    if initial_train_size is not None and initial_train_size > len(y):
        raise Exception(
            'If used, `initial_train_size` must be smaller than lenght of `y`.'
        )
        
    if initial_train_size is not None and initial_train_size < forecaster.window_size:
        raise Exception(
            f"`initial_train_size` must be greater than "
            f"forecaster's window_size ({forecaster.window_size})."
        )

    if initial_train_size is None and not forecaster.fitted:
        raise Exception(
            '`forecaster` must be already trained if no `initial_train_size` is provided.'
        )

    if initial_train_size is None and forecaster.fitted:
        logging.warning(
            f'Altough no initial train is done, the first '
            f'{len(forecaster.last_window)} observations are needed to create '
            f'the initial predictors. Therefore, no predictions are calculated for them.'
        )

    metric = get_metric(metric=metric)
    backtest_predictions = []

        
    if initial_train_size is not None:
        if exog is None:
            forecaster.fit(y=y[:initial_train_size])      
        else:
            forecaster.fit(y=y[:initial_train_size], exog=exog[:initial_train_size])
        window_size = forecaster.window_size
    else:
        # Although not used for training, first observations are needed to create the initial predictors
        window_size = forecaster.window_size
        initial_train_size = window_size
    
    folds     = (len(y) - initial_train_size) // steps + 1
    remainder = (len(y) - initial_train_size) % steps
    
    if verbose:
        print(f"Number of observations used for training or as initial window: {initial_train_size}")
        print(f"Number of observations used for testing: {len(y) - initial_train_size}")
        print(f"    Number of folds: {folds - 1 * (remainder == 0)}")
        print(f"    Number of steps per fold: {steps}")
        if remainder != 0:
            print(f"    Last fold only includes {remainder} observations")
    
    for i in range(folds):
        
        last_window_end   = initial_train_size + i * steps
        last_window_start = (initial_train_size + i * steps) - window_size 
        last_window_y     = y[last_window_start:last_window_end]
        if exog is not None:
            next_window_exog    = exog[last_window_end:last_window_end + steps]
                
        if i < folds - 1:
            if exog is None:
                pred = forecaster.predict_interval(
                            steps       = steps,
                            last_window = last_window_y,
                            interval    = interval,
                            n_boot      = n_boot,
                            in_sample_residuals = in_sample_residuals
                        )
            else:
                pred = forecaster.predict_interval(
                            steps       = steps,
                            last_window = last_window_y,
                            exog        = next_window_exog,
                            interval    = interval,
                            n_boot      = n_boot,
                            in_sample_residuals = in_sample_residuals
                        )
        elif remainder != 0:
            steps = remainder 
            if exog is None:
                pred = forecaster.predict_interval(
                            steps       = steps,
                            last_window = last_window_y,
                            interval    = interval,
                            n_boot      = n_boot,
                            in_sample_residuals = in_sample_residuals
                        )
            else:
                pred = forecaster.predict_interval(
                            steps       = steps,
                            last_window = last_window_y,
                            exog        = next_window_exog,
                            interval    = interval,
                            n_boot      = n_boot,
                            in_sample_residuals = in_sample_residuals
                        )
        else:
            continue
        
        backtest_predictions.append(pred)
    
    backtest_predictions = np.concatenate(backtest_predictions)
    metric_value = metric(
                        y_true = y[initial_train_size:],
                        y_pred = backtest_predictions[:, 0]
                   )
    
    if set_out_sample_residuals:
        if not isinstance(forecaster, ForecasterAutoregMultiOutput):
            forecaster.set_out_sample_residuals(
                y[initial_train_size: initial_train_size + len(backtest_predictions)] - backtest_predictions[:, 0]
            )

    return np.array([metric_value]), backtest_predictions