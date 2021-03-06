




import os
import argparse
from utils import load_config
from data_process import build_dataloader
from data_process import data_info_process
from data_process import additional_data_process
from model import CrossEncoder
from model import load_cross_encoder_model
from utils import evaluation
import spacy
nlp = spacy.load("en_core_web_sm")

#cuda device
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


# data process config 
data_process_cfg = load_config(path='config/data_process.yaml')

# model config
model_cfg = load_config(path='config/model_mse/model.yaml')


# parameter setting
parser = argparse.ArgumentParser()
parser.add_argument("--data_process_cfg", type=dict, default=data_process_cfg, help="None")
parser.add_argument("--model_cfg", type=dict, default=model_cfg, help="None")
parser.add_argument("--nlp", type=None, default=nlp, help="None")
args = parser.parse_args()
print(args)


# data process 
data_info = data_info_process(args=args)


data_info['train_data_x'] = data_info['train_data_x'][:100]
data_info['train_data_y'] = data_info['train_data_y'][:100]


# additional data process
data_info = additional_data_process(data_info=data_info, args=args)



if args.model_cfg['only_eval'] is False:
    # build dataloader for trainig
    train_dataloader = build_dataloader(train_data_x=data_info['train_data_x'], 
                                        train_data_y=data_info['train_data_y'],
                                        pd2data=data_info['pd2data'],
                                        args=args)



    # modeling
    cross_encoder_model = CrossEncoder(args=args)
    cross_encoder_model.fit(train_dataloader=train_dataloader)
    cross_encoder_model.save()



# load model
auto_model, auto_trf = load_cross_encoder_model(args=args)




# evaluation for validation
evaluation(query_list=data_info['val_data_test'], 
           query2data=data_info['query2val_data'], 
           pd2data=data_info['pd2data'], 
           auto_model=auto_model, 
           auto_trf=auto_trf, 
           args=args,
           category='Validation')



# evaluation for train
train_query = list(set([q for q, p in data_info['train_data_x']]))

evaluation(query_list=train_query, 
           query2data=data_info['query2train_data'], 
           pd2data=data_info['pd2data'], 
           auto_model=auto_model, 
           auto_trf=auto_trf, 
           args=args,
           category='Train')








