


import random
import pandas as pd
from tqdm import tqdm
from torch.utils.data import DataLoader
from sentence_transformers import InputExample, losses

from util import convert_q_pdi_to_q_sent_feature

 


def data_process(args=None):
    # load data (task1)
    print('load data ...')
    path = 'task_1_query-product_ranking/'
    train_path = path + 'train-v0.2.csv'
    test_path = path + 'test_public-v0.2.csv'
    product_path = path + 'product_catalogue-v0.2.csv'
    submit_path = path + 'sample_submission-v0.2.csv'
    task2_path = 'task_2_multiclass_product_classification/'

    train_dat = pd.read_csv(train_path)
    test_dat = pd.read_csv(test_path)
    product_dat = pd.read_csv(product_path)
    submit_dat = pd.read_csv(submit_path)
    
    # load data (task2)
    task2_path = 'task_2_multiclass_product_classification/'
    task2_train_path = task2_path + 'train-v0.2.csv'
    task2_product_path = task2_path + 'product_catalogue-v0.2.csv'

    task2_train_dat = pd.read_csv(task2_train_path)
    task2_product_dat = pd.read_csv(task2_product_path)


    # imputation
    print('imputation ...')
    train_dat = train_dat.fillna('Empty')
    test_dat = test_dat.fillna('Empty')
    product_dat = product_dat.fillna('Empty')
    task2_train_dat = task2_train_dat.fillna('Empty')
    task2_product_dat = task2_product_dat.fillna('Empty')


    # add product_new_id
    print('add product_new_id ...')
    product_dat = build_product_idx(product_dat, locale_name='product_locale')
    train_dat = build_product_idx(train_dat, locale_name='query_locale')
    test_dat = build_product_idx(test_dat, locale_name='query_locale')
    task2_product_dat = build_product_idx(task2_product_dat, locale_name='product_locale')
    task2_train_dat = build_product_idx(task2_train_dat, locale_name='query_locale')


    # choose given locale
    print('choose given locale ...')
    dat_lc = train_dat[train_dat['query_locale'].isin(args.target_query_locale)]
    test_dat_lc = test_dat[test_dat['query_locale'].isin(args.target_query_locale)]
    task2_train_dat_lc = task2_train_dat[task2_train_dat['query_locale'].isin(args.target_query_locale)]


    # split train, val data by random_select (task1)
    print('split train, val data by random_select ...')
    query_list = list(set(dat_lc['query']))
    train_N = int(args.train_val_rate * len(query_list))
    given_query_list = random.sample(query_list, len(query_list))
    train_query_list = given_query_list[:train_N]
    val_query_list = given_query_list[train_N:]
    train_dat_lc = dat_lc[dat_lc['query'].isin(train_query_list)]
    val_dat_lc = dat_lc[dat_lc['query'].isin(val_query_list)]


    # build task2 complement query (task2)
    task2_query_set = set(task2_train_dat_lc['query'])
    task2_complement_query_list = list(task2_query_set - set(query_list))
    N = int(len(task2_complement_query_list) * args.task2_used_rate)
    task2_complement_query_list = random.sample(task2_complement_query_list, N)
    task2_complement_dat_lc = task2_train_dat_lc[task2_train_dat_lc['query'].isin(task2_complement_query_list)]


    # build given_product_dat (task1)
    train_pd_set = set(train_dat_lc['product_new_id'])
    val_pd_set = set(val_dat_lc['product_new_id'])
    test_pd_set = set(test_dat_lc['product_new_id'])
    all_pd_list = list(train_pd_set | val_pd_set | test_pd_set)
    given_product_dat = product_dat[product_dat['product_new_id'].isin(all_pd_list)]


    # build given_product_dat (task2)
    task2_pd_list = list(set(task2_complement_dat_lc['product_new_id']))
    given_task2_product_dat = task2_product_dat[task2_product_dat['product_new_id'].isin(task2_pd_list)]


    # build pd2data
    print('build pd2data ...')
    pd2data = build_pd2data(given_product_dat=given_product_dat)
    task2_pd2data = build_pd2data(given_product_dat=given_task2_product_dat)
    pd2data = left_join_map_merge(left_map=pd2data, right_map=task2_pd2data)


    # build query2data
    print('build query2data ...')
    query2train_data = build_query2data(target_dat=train_dat_lc, target_query_locale=args.target_query_locale)
    query2val_data = build_query2data(target_dat=val_dat_lc, target_query_locale=args.target_query_locale)
    query2test_data = build_query2data(target_dat=test_dat_lc, target_query_locale=args.target_query_locale)
    query2complement_data = build_query2data(target_dat=task2_complement_dat_lc, target_query_locale=args.target_query_locale)
    if args.use_task2_data is True: 
        query2train_data = left_join_map_merge(left_map=query2train_data, right_map=query2complement_data)


    # build train_data_x, train_data_y
    print('build train_data_x, train_data_y ...')
    train_data_x, train_data_y = [], []
    train_data_x, train_data_y = update_train_data_x_y(query2data=query2train_data, 
                                                       train_data_x=train_data_x, 
                                                       train_data_y=train_data_y, 
                                                       args=args)


    # build val_data_x
    print('build val_data_x ...')
    val_data_x = []
    for query in list(query2val_data.keys()):
        val_data_x.append(query)

    return train_data_x, train_data_y , val_data_x, query2train_data, query2val_data, query2test_data, pd2data





def build_product_idx(dat, locale_name='product_locale'):
    pd_idx_list = []
    for records in dat.to_dict('records'):
        product_id = records['product_id']
        product_locale = records[locale_name]
        pd_idx = product_id + '@' + product_locale
        pd_idx_list.append(pd_idx)
    dat['product_new_id'] = pd_idx_list
    return dat





def build_query2data(target_dat, target_query_locale):
    esci_label2gain = {
                       'exact' : 1,
                       'substitute' : 0.1,
                       'complement' : 0.01,
                       'irrelevant' : 0.0,
                      }
    query2data = dict()
    for records in target_dat.to_dict('records'):
        query = records['query']
        #query_id = records['query_id']
        product_new_id = records['product_new_id']
        query_locale = records['query_locale']
        product_id = records['product_id']
        if 'query_id'  in records:
            query_id = records['query_id']
        else:
            query_id = None
        product_locale = product_new_id.split('@')[1]
        if query_locale in target_query_locale and query not in query2data:
            query2data[query] = {
                                 'pos' : [],
                                 'neg' : [],
                                 'all' : [],
                                 'locale' : query_locale,
                                 'query_id' : query_id,
                                 'data' : []
                                 }
        if 'esci_label' in records:
            if records['esci_label'] == 'exact':
                query2data[query]['pos'].append(product_new_id)
            else:
                query2data[query]['neg'].append(product_new_id)
            gain = esci_label2gain[records['esci_label'] ]
        else:
            gain = None
        query2data[query]['all'].append(product_new_id)
        query2data[query]['data'].append({
                                          'gain' : gain, 
                                           'product_new_id' : product_new_id, 
                                           'product_id':product_id
                                         })
    return query2data



 
 
def build_dataloader(train_data_x=None, 
                     train_data_y=None,
                     pd2data=dict,
                     args=None):

    # convert query_id, pdi into text
    head_tail_list, sent_length = convert_q_pdi_to_q_sent_feature(q_pdi_list=train_data_x,
                                                                  pd2data=pd2data,
                                                                  eval_mode=False,
                                                                  args=args)
    label_list = train_data_y
    
    # convert into train_dataloader
    train_samples = []
    if args.contractive_loss is False:
        for i, (query, passage) in enumerate(head_tail_list):
            gain_y = label_list[i]
            train_samples.append(InputExample(texts=[query, passage], label=float(gain_y)))
    else:
        for i, (query, passage, pos, neg) in enumerate(head_tail_list):
            gain_y = label_list[i]
            train_samples.append(InputExample(texts=[query, passage, pos, neg], label=float(gain_y)))
    train_dataloader = DataLoader(train_samples, shuffle=True, batch_size=args.batch_size, drop_last=True)
    return train_dataloader





def data_process_denoise(train_data_x=list, train_data_y=list, query2train_data=dict, args=None):
    # init
    train_data_x_update, train_data_y_update = list(), list()
    query_list = list(query2train_data.keys())
    train_data_x
    index_list = [i for i in range(len(train_data_x))]


    # main
    if args.denoise_mode is None:
        train_data_x_update = train_data_x
        train_data_y_update = train_data_y
    elif args.denoise_mode == 'random-query':
        denoise_query = random.sample(query_list, int(len(query_list) * args.denoise_rate))
        denoise_query_set = set(denoise_query)
        for i, (query, pdi) in enumerate(train_data_x):
            if query not in denoise_query_set:
                train_data_x_update.append([query, pdi])
                train_data_y_update.append(train_data_y[i])
    elif args.denoise_mode == 'random-records':
        denoise_index = random.sample(index_list, int(len(index_list) * args.denoise_rate))
        denoise_index_set = set(denoise_index)
        for i, (query, pdi) in enumerate(train_data_x):
            if i not in denoise_index_set:
                train_data_x_update.append([query, pdi])
                train_data_y_update.append(train_data_y[i])
    elif args.denoise_mode == 'undersampling':
        # gain2data
        # determine data_len for each gain
        # randm sample
        N = 0

    return train_data_x_update, train_data_y_update





def build_pd2data(given_product_dat=None):
    # build pd2data
    pd2data = dict()
    for records in given_product_dat.to_dict('records'):
        product_id = records['product_id']
        product_new_id = records['product_new_id']
        product_locale = records['product_locale']
        product_title = records['product_title']
        product_bullet_point = records['product_bullet_point']
        product_brand = records['product_brand']
        product_color_name = records['product_color_name']
        product_description = records['product_description']
        origin_super_sents = product_bullet_point.split('\n')
        super_sents = product_brand + '. ' + product_color_name + '. ' + product_bullet_point + '. ' + product_description + '.'
        if product_new_id not in pd2data:
            pd2data[product_new_id] = {
                                    'product_title' : product_title,
                                    'product_bullet_point' : product_bullet_point,
                                    'super_sents' : super_sents,
                                    'origin_super_sents' : origin_super_sents,
                                    'product_brand' : product_brand,
                                    'product_color_name' : product_color_name,
                                    'product_id' : product_id
                                    }
    return pd2data





def update_train_data_x_y(query2data=dict, train_data_x=list, train_data_y=list, args=None):
    for query in list(query2data.keys()):
        pos_set = query2data[query]['pos']
        neg_set = query2data[query]['neg']
        data_list = query2data[query]['data']

        all_pos_set = set([data['product_new_id'] for data in data_list if data['gain'] != 0.0])
        all_neg_set = set(query2data[query]['all']) - all_pos_set
        pos_sample = set(random.sample(list(all_pos_set ), min(len(all_pos_set), len(all_neg_set))))

        exact_data = []
        substitute_data = []
        complement_data = []
        irrelevant_data = []
        train_data_x_batch = []
        train_data_y_batch = []
        for data in data_list:
            product_new_id = data['product_new_id']
            gain = data['gain']
            train_data_x_batch.append([query, product_new_id])
            train_data_y_batch.append(gain)
            if gain == 1.0:
                exact_data.append(product_new_id)
            elif gain == 0.1:
                substitute_data.append(product_new_id)
            elif gain == 0.01:
                complement_data.append(product_new_id)
            else:
                irrelevant_data.append(product_new_id)
        if len(train_data_x_batch) > 0:
            if len(complement_data + irrelevant_data) > 0:
                if len(exact_data) + len(substitute_data) > 0:
                    neg_data = complement_data + irrelevant_data
                    pos_data = exact_data + substitute_data
                else:
                    if len(complement_data) > 0 and len(irrelevant_data) > 0:
                        neg_data = irrelevant_data
                        pos_data = complement_data
                    else:
                        neg_data = irrelevant_data + complement_data
                        pos_data = irrelevant_data + complement_data
            elif len(complement_data + irrelevant_data) == 0:
                if len(exact_data) > 0 and len(substitute_data) > 0:
                    neg_data = substitute_data
                    pos_data = exact_data
                else:
                    neg_data = substitute_data + exact_data
                    pos_data = substitute_data + exact_data
            if args.contractive_loss is True:
                index = 0
                while index != len(train_data_x_batch):
                    neg_pdi = neg_data[index % len(neg_data)]
                    pos_pdi = random.sample(pos_data, 1)[0]
                    train_data_x_batch[index] = train_data_x_batch[index] + [pos_pdi, neg_pdi]
                    index +=1
            train_data_x += train_data_x_batch
            train_data_y += train_data_y_batch
    return train_data_x, train_data_y





def left_join_map_merge(left_map=dict, right_map=dict):
    right_key_list = list(right_map.keys())
    for right_key in right_key_list:
        if right_key not in left_map:
            left_map[right_key] = right_map[right_key]
    return left_map








