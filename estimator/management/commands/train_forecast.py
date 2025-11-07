import pandas as pd
from django.core.management.base import BaseCommand
from estimator.models import MaterialPrice, Forecast
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
import numpy as np


class Command(BaseCommand):
    help = "Train models and forecast next quarter"

    def handle(self, *args, **options):
        next_q, next_y = MaterialPrice.next_quarter()
        Forecast.objects.filter(quarter=next_q, year=next_y).delete()

        materials = MaterialPrice.objects.values('description').distinct()
        for mat in materials:
            desc = mat['description']
            data = MaterialPrice.objects.filter(description=desc).order_by('year', 'quarter')
            if data.count() < 4:
                continue

            df = pd.DataFrame(list(data.values('quarter', 'year', 'rate')))
            df['q_num'] = df['quarter'].map({'Q1':1, 'Q2':2, 'Q3':3, 'Q4':4})
            df['time'] = df['year'] * 4 + df['q_num']
            X = df[['time']].values
            y = df['rate'].values

            # Linear
            lr = LinearRegression().fit(X, y)
            next_time = (next_y * 4) + {'Q1':1, 'Q2':2, 'Q3':3, 'Q4':4}[next_q]
            pred_lr = max(0, lr.predict([[next_time]])[0])

            # RF
            rf = RandomForestRegressor(n_estimators=10).fit(X, y)
            pred_rf = max(0, rf.predict([[next_time]])[0])

            Forecast.objects.create(
                material_description=desc,
                model_type='linear',
                quarter=next_q,
                year=next_y,
                forecasted_price=round(pred_lr, 2)
            )
            Forecast.objects.create(
                material_description=desc,
                model_type='random_forest',
                quarter=next_q,
                year=next_y,
                forecasted_price=round(pred_rf, 2)
            )

        self.stdout.write(self.style.SUCCESS(f"Forecasted {next_q} {next_y}"))