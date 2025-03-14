
import random
import pandas as pd
import time
import numpy as np
from collections import defaultdict
from sklearn.linear_model import LogisticRegression
from tableone import TableOne

def randomAssignment(
        data, 
        subjectID, 
        nVisits, 
        seed,
        nIter,
        batchSize, 
        nBatches
        ):

    t1 = time.time()
    randomized_assignments = []
    random.seed(seed)

    for _ in range(nIter): 
        subjects = data[[subjectID, nVisits]].itertuples(index=False, name=None)
        subjects = list(subjects) 
        random.shuffle(subjects) 

        batches = [defaultdict(int) for _ in range(nBatches)]
        batch_totals = np.zeros(nBatches, dtype=int)  

        for subj, visits in subjects:
            for i in range(nBatches):
                if batch_totals[i] + visits <= batchSize:
                    batches[i][subj] = visits
                    batch_totals[i] += visits
                    break
        
        assigned_subjects = set()
        for batch in batches:
            assigned_subjects.update(batch.keys())

        leftover = {}
        for subject, visits in subjects:
            if subject not in assigned_subjects:
                leftover[subject] = visits
        if leftover:
            batches.append(leftover)

        randomized_assignments.append(batches)

    t2 = time.time()
    print(f'Ran {nIter} iterations in {t2-t1:.1f} seconds\n')
    print(f'Total samples to analyze: {data[nVisits].sum()}\n')
    print(f'Total subjects to analyze: {len(data)}\n')
    print(f'Printing iteration #1: {randomized_assignments[0]}\n')

    return randomized_assignments


def propensity_scores(data, subject_id, covariates, randomized_assignments):
    # Convert dictonary format of randomized_assignments to a list within each iteration
    t3 = time.time()
    assignments_list = []
    for i in randomized_assignments:
        listed_subjectID = [] 
        for batch in i:
            subject_ids = list(batch.keys())
            listed_subjectID.append(subject_ids)
        assignments_list.append(listed_subjectID)

    # propensity score metrics
    metrics = []
    for i, iteration in enumerate(assignments_list, start=1):
        batch_diffs = []
        for batch in iteration:
            temp_data = data.copy()
            temp_data['batch'] = temp_data[subject_id].isin(batch).astype(int)
            
            # Logistic Regression
            model = LogisticRegression()
            model.fit(temp_data[covariates], temp_data['batch'])
            temp_data['propensity_score'] = model.predict_proba(temp_data[covariates])[:, 1]
            
            # Difference btwn in-group and out-group propensity scores
            in_batch = temp_data.loc[temp_data['batch'] == 1, 'propensity_score']
            out_batch = temp_data.loc[temp_data['batch'] == 0, 'propensity_score']
            diff = abs(in_batch.mean() - out_batch.mean())
            batch_diffs.append(diff)
        
        # Average balance (in-group vs out-group) for the iteration
        avg_balance = np.mean(batch_diffs) # want as low as possible
        metrics.append((i, avg_balance))
    
    metrics_df = pd.DataFrame(metrics, columns=['Iteration', 'avg_balance'])
    
    lowest_balance = metrics_df.sort_values('avg_balance').iloc[0]['Iteration'] - 1
    lowest_balance_score = metrics_df.sort_values('avg_balance').iloc[0]['avg_balance']
    best_batches = assignments_list[int(lowest_balance)]
    
    # Add batch num to original dataset
    data['Batch_Assignment'] = None
    for batch_num, group in enumerate(best_batches, start=1):
        data.loc[data[subject_id].isin(group), 'Batch_Assignment'] = batch_num
    
    t4 = time.time()
    print(f'Ran in {((t4-t3)/60):.1f} minutes')
    print(f'Lowest balance score: {lowest_balance_score:.4f}')

    return data, metrics_df


# Data 
file_path = 'C:\\Users\\wingersm\\OneDrive - The University of Colorado Denver\\Desktop\\Python Projects\\2.0 Blood Randomization\\Data\\Blood_randomization_3.11.25.xlsx'
df = pd.read_excel(file_path)

# Adjust columns
df['site'] = df['site'].astype('category')
df['blinded_random_assignment'] = df['blinded_random_assignment'].astype('category')
df['fivep_sex'] = df['fivep_sex'].replace({2: 1})
df['fivep_sex'] = df['fivep_sex'].astype('category')
print(df.head())

# Random Assignment
assignments = randomAssignment(
                    data = df, 
                    subjectID = 'id', 
                    nVisits = 'nVisits', 
                    seed = 1989,
                    nIter = 50000,
                    batchSize = 34, 
                    nBatches = 4
                    )

# Define factors for balancing (covariates)
covariates = ['site', 'blinded_random_assignment', 'doi_to_v1', 'fivep_sex']  

# Propensity scores
data, metrics = propensity_scores(
                        data = df, 
                        subject_id = 'id',
                        covariates = covariates, 
                        randomized_assignments = assignments)


# Summary
summary = TableOne(
    data, 
    columns= ['site', 'blinded_random_assignment', 'doi_to_v1', 'fivep_sex', 'nVisits'],
    categorical= ['site', 'blinded_random_assignment', 'fivep_sex'],
    continuous= ['doi_to_v1', 'nVisits'], 
    groupby='Batch_Assignment',
    pval=True,
    decimals=2)
print(summary.tabulate(tablefmt = "fancy_grid"))

# Summary w/out leftovers
data_filtered = data[data['Batch_Assignment'] != 5]
summary2 = TableOne(
    data_filtered, 
    columns= ['site', 'blinded_random_assignment', 'doi_to_v1', 'fivep_sex', 'nVisits'],
    categorical= ['site', 'blinded_random_assignment', 'fivep_sex'],
    continuous= ['doi_to_v1', 'nVisits'], 
    groupby='Batch_Assignment',
    pval=True,
    decimals=2)
print(summary2.tabulate(tablefmt = "fancy_grid"))

# Save
save_path = 'C:\\Users\\wingersm\\OneDrive - The University of Colorado Denver\\Desktop\\Python Projects\\2.0 Blood Randomization\\Data\\Blood_randomization_3.11.25_results.xlsx'
data.to_excel(save_path, index=False)
print("saved!")


data_bdnf = data.copy()
data_bdnf = data_bdnf[data_bdnf['Batch_Assignment'] !=5]
data_bdnf['Batch_Assignment'] = data_bdnf['Batch_Assignment'].replace({2: 1})
data_bdnf['Batch_Assignment'] = data_bdnf['Batch_Assignment'].replace({4: 3})

summary3 = TableOne(
    data_bdnf, 
    columns= ['site', 'blinded_random_assignment', 'doi_to_v1', 'fivep_sex', 'nVisits'],
    categorical= ['site', 'blinded_random_assignment', 'fivep_sex'],
    continuous= ['doi_to_v1', 'nVisits'], 
    groupby='Batch_Assignment',
    pval=True,
    decimals=2)
print(summary3.tabulate(tablefmt = "fancy_grid"))