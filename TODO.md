Backtesting `backtesting_forecaster()`:
    [] The current implementation of `backtesting_forecaster()` always do an initial training. Allow `backtesting_forecaster()` to backtest forecasters already trained.
    [] Include an argument `refit` to decide if the forecaster is retrained in each iteration.
    [] Currently, backtesting ForecasterAutoregMultiOutput do not allow for incomplete folds. Allow it including dummy values fo the remaining steps of the last fold and removing then the corresponding predictions.
    [] Create a function to select the metric  
    [] Add option to update out_sample_residuals at the end of the proces of backtesting

Cross validation `cv_forecaster()`:
    [] Currently, cv ForecasterAutoregMultiOutput do not allow for incomplete folds. Allow it including dummy values fo the remaining steps of the last fold and removing then the corresponding predictions.
    [] Create a function to select the metric  
    [] Add option to update out_sample_residuals at the end of the proces of cv

ForecasterCustom
    [] Remove ForecasterCustom class


