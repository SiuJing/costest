# estimator/ml_forecast.py
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from django.db import transaction
from .models import ProjectItem, Forecast, MaterialPrice, LabourRate, Project
import numpy as np
import logging

logger = logging.getLogger(__name__)

def run_forecast(project_id):
    project = Project.objects.get(pk=project_id)
    items = ProjectItem.objects.filter(project=project)
    forecasts = []

    # Get the next quarter/year from the latest data
    material_next_q, material_next_y = MaterialPrice.next_quarter()
    labour_next_q, labour_next_y = LabourRate.next_quarter()
    
    print(f"🔮 Forecasting materials for {material_next_q} {material_next_y}")
    print(f"🔮 Forecasting labour for {labour_next_q} {labour_next_y}")
    print(f"📋 Processing {items.count()} project items")

    # Delete existing forecasts for this project
    Forecast.objects.filter(project=project).delete()

    materials_processed = 0
    labour_processed = 0
    
    for item in items:
        print(f"🔍 Processing: {item.description} (Section: {item.section})")
        
        # Try to find in Material prices first
        material_history = None
        labour_history = None
        
        # Material search strategies
        material_strategies = [
            lambda: MaterialPrice.objects.filter(
                section=item.section,
                description__iexact=item.description
            ).order_by('year', 'quarter'),
            
            lambda: MaterialPrice.objects.filter(
                section=item.section,
                description__icontains=item.description
            ).order_by('year', 'quarter'),
            
            lambda: MaterialPrice.objects.filter(
                description__iexact=item.description
            ).order_by('year', 'quarter'),
        ]
        
        # Labour search strategies  
        labour_strategies = [
            lambda: LabourRate.objects.filter(
                section=item.section,
                description__iexact=item.description
            ).order_by('year', 'quarter'),
            
            lambda: LabourRate.objects.filter(
                section=item.section, 
                description__icontains=item.description
            ).order_by('year', 'quarter'),
            
            lambda: LabourRate.objects.filter(
                description__iexact=item.description
            ).order_by('year', 'quarter'),
        ]
        
        # DEBUG: Check what's available in both models
        material_exact = MaterialPrice.objects.filter(
            section=item.section,
            description__iexact=item.description
        )
        labour_exact = LabourRate.objects.filter(
            section=item.section,
            description__iexact=item.description
        )
        
        print(f"   🔎 Material exact match: {material_exact.count()} records")
        print(f"   🔎 Labour exact match: {labour_exact.count()} records")
        
        # Try material strategies
        for i, strategy in enumerate(material_strategies):
            potential_history = strategy()
            if potential_history.count() >= 2:
                material_history = potential_history
                print(f"   ✅ Found {material_history.count()} MATERIAL records using strategy {i+1}")
                break
        
        # Try labour strategies if no material found
        if not material_history:
            for i, strategy in enumerate(labour_strategies):
                potential_history = strategy()
                if potential_history.count() >= 2:
                    labour_history = potential_history
                    print(f"   ✅ Found {labour_history.count()} LABOUR records using strategy {i+1}")
                    break
        
        if not material_history and not labour_history:
            print(f"   ❌ No historical data found for: {item.description}")
            # DEBUG: Show what we did find
            material_any = MaterialPrice.objects.filter(description__icontains=item.description)
            labour_any = LabourRate.objects.filter(description__icontains=item.description)
            print(f"   🔍 Material any match: {material_any.count()} records")
            print(f"   🔍 Labour any match: {labour_any.count()} records")
            continue

        # Use whichever history we found
        history = material_history or labour_history
        forecast_type = 'material' if material_history else 'labour'
        next_q = material_next_q if material_history else labour_next_q
        next_y = material_next_y if material_history else labour_next_y

        try:
            # Prepare data for ML
            df = pd.DataFrame(list(history.values('quarter', 'year', 'rate')))
            
            # Create a simple time series
            df = df.sort_values(['year', 'quarter'])
            df['time_index'] = range(len(df))
            
            X = df[['time_index']].values
            y = df['rate'].values

            if len(X) < 3:
                X_train, y_train = X, y
                if len(X) == 2:
                    trend = y[1] - y[0]
                    prediction = y[-1] + trend
                else:
                    prediction = y[0]
                
                lr_pred = max(0, float(prediction))
                rf_pred = max(0, float(prediction))
                
            else:
                X_train, y_train = X, y
                
                # Linear Regression
                lr = LinearRegression()
                lr.fit(X_train, y_train)
                lr_pred = max(0, float(lr.predict([[len(X)]])[0]))
                
                # Random Forest
                rf = RandomForestRegressor(n_estimators=10, random_state=42)
                rf.fit(X_train, y_train)
                rf_pred = max(0, float(rf.predict([[len(X)]])[0]))

            reasonable_range = (0.1, 1000000)
            
            if reasonable_range[0] <= lr_pred <= reasonable_range[1]:
                forecasts.append(Forecast(
                    project=project,
                    material_description=f"{forecast_type.upper()}: {item.description}",
                    model_type='linear',
                    quarter=next_q,
                    year=next_y,
                    forecasted_price=round(lr_pred, 2)
                ))
                if forecast_type == 'material':
                    materials_processed += 1
                else:
                    labour_processed += 1
                print(f"   📈 Linear forecast: RM{lr_pred:.2f} ({forecast_type})")

            if reasonable_range[0] <= rf_pred <= reasonable_range[1]:
                forecasts.append(Forecast(
                    project=project,
                    material_description=f"{forecast_type.upper()}: {item.description}",
                    model_type='random_forest', 
                    quarter=next_q,
                    year=next_y,
                    forecasted_price=round(rf_pred, 2)
                ))
                if forecast_type == 'material':
                    materials_processed += 1
                else:
                    labour_processed += 1
                print(f"   🌲 Random Forest forecast: RM{rf_pred:.2f} ({forecast_type})")

        except Exception as e:
            print(f"   ❌ Error forecasting {item.description}: {str(e)}")
            continue

    # Save all forecasts
    if forecasts:
        Forecast.objects.bulk_create(forecasts)
        print(f"🎯 Created {len(forecasts)} forecasts for {materials_processed} materials and {labour_processed} labour items")
    else:
        print("⚠️  No forecasts created")

    return len(forecasts)