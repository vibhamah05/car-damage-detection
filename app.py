try:
    import detectron2
except:
    import os
    os.system('pip install git+https://github.com/facebookresearch/detectron2.git')

import os
import streamlit as st
from PIL import Image
from matplotlib.pyplot import axis
import requests
import numpy as np
from torch import nn
import requests
from annotated_text import annotated_text
from streamlit_option_menu import option_menu
import torch
import detectron2
from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog
from detectron2.utils.visualizer import ColorMode

damage_model_path = 'model_final_damage.pth'
scratch_model_path = 'model_final_scratch.pth'
parts_model_path = 'model_final_parts.pth'

if torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'

cfg_scratches = get_cfg()
cfg_scratches.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
cfg_scratches.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.8
cfg_scratches.MODEL.ROI_HEADS.NUM_CLASSES = 1
cfg_scratches.MODEL.WEIGHTS = scratch_model_path
cfg_scratches.MODEL.DEVICE = device

predictor_scratches = DefaultPredictor(cfg_scratches)

metadata_scratch = MetadataCatalog.get("car_dataset_val")
metadata_scratch.thing_classes = ["scratch"]

cfg_damage = get_cfg()
cfg_damage.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
cfg_damage.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7
cfg_damage.MODEL.ROI_HEADS.NUM_CLASSES = 1
cfg_damage.MODEL.WEIGHTS = damage_model_path
cfg_damage.MODEL.DEVICE = device

predictor_damage = DefaultPredictor(cfg_damage)

metadata_damage = MetadataCatalog.get("car_damage_dataset_val")
metadata_damage.thing_classes = ["damage"]

cfg_parts = get_cfg()
cfg_parts.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
cfg_parts.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.75
cfg_parts.MODEL.ROI_HEADS.NUM_CLASSES = 19
cfg_parts.MODEL.WEIGHTS = parts_model_path
cfg_parts.MODEL.DEVICE = device

predictor_parts = DefaultPredictor(cfg_parts)

metadata_parts = MetadataCatalog.get("car_parts_dataset_val")
metadata_parts.thing_classes = ['_background_',
 'back_bumper',
 'back_glass',
 'back_left_door',
 'back_left_light',
 'back_right_door',
 'back_right_light',
 'front_bumper',
 'front_glass',
 'front_left_door',
 'front_left_light',
 'front_right_door',
 'front_right_light',
 'hood',
 'left_mirror',
 'right_mirror',
 'tailgate',
 'trunk',
 'wheel']

def merge_segment(pred_segm):
    merge_dict = {}
    for i in range(len(pred_segm)):
        merge_dict[i] = []
        for j in range(i+1,len(pred_segm)):
            if torch.sum(pred_segm[i]*pred_segm[j])>0:
                merge_dict[i].append(j)
    
    to_delete = []
    for key in merge_dict:
        for element in merge_dict[key]:
            to_delete.append(element)
    
    for element in to_delete:
        merge_dict.pop(element,None)
        
    empty_delete = []
    for key in merge_dict:
        if merge_dict[key] == []:
            empty_delete.append(key)
    
    for element in empty_delete:
        merge_dict.pop(element,None)
        
    for key in merge_dict:
        for element in merge_dict[key]:
            pred_segm[key]+=pred_segm[element]
            
    except_elem = list(set(to_delete))
    
    new_indexes = list(range(len(pred_segm)))
    for elem in except_elem:
        new_indexes.remove(elem)
        
    return pred_segm[new_indexes]

def inference(image):
    img = np.array(image)
    outputs_damage = predictor_damage(img)
    outputs_parts = predictor_parts(img)
    outputs_scratch = predictor_scratches(img)
    out_dict = outputs_damage["instances"].to("cpu").get_fields()
    merged_damage_masks = merge_segment(out_dict['pred_masks'])
    scratch_data = outputs_scratch["instances"].get_fields()
    scratch_masks = scratch_data['pred_masks']
    damage_data = outputs_damage["instances"].get_fields()
    damage_masks = damage_data['pred_masks']
    parts_data = outputs_parts["instances"].get_fields()
    parts_masks = parts_data['pred_masks']
    parts_classes = parts_data['pred_classes']
    new_inst = detectron2.structures.Instances((1024,1024))
    new_inst.set('pred_masks',merge_segment(out_dict['pred_masks']))
    
    parts_damage_dict = {}
    parts_list_damages = []
    for part in parts_classes:
        parts_damage_dict[metadata_parts.thing_classes[part]] = []
    for mask in scratch_masks:
        for i in range(len(parts_masks)):
            if torch.sum(parts_masks[i]*mask)>0:
                parts_damage_dict[metadata_parts.thing_classes[parts_classes[i]]].append('scratch')
                parts_list_damages.append(f'{metadata_parts.thing_classes[parts_classes[i]]} has scratch')              
                print(f'{metadata_parts.thing_classes[parts_classes[i]]} has scratch')
    for mask in merged_damage_masks:
        for i in range(len(parts_masks)):
            if torch.sum(parts_masks[i]*mask)>0:
                parts_damage_dict[metadata_parts.thing_classes[parts_classes[i]]].append('damage')
                parts_list_damages.append(f'{metadata_parts.thing_classes[parts_classes[i]]} has damage')
                print(f'{metadata_parts.thing_classes[parts_classes[i]]} has damage')

    v_d = Visualizer(img[:, :, ::-1],
                   metadata=metadata_damage, 
                   scale=0.5, 
                   instance_mode=ColorMode.SEGMENTATION   # remove the colors of unsegmented pixels. This option is only available for segmentation models
    )
    #v_d = Visualizer(img,scale=1.2)
    #print(outputs["instances"].to('cpu'))
    out_d = v_d.draw_instance_predictions(new_inst)
    img1 = out_d.get_image()[:, :, ::-1]

    v_s = Visualizer(img[:, :, ::-1],
                   metadata=metadata_scratch, 
                   scale=0.5, 
                   instance_mode=ColorMode.SEGMENTATION   # remove the colors of unsegmented pixels. This option is only available for segmentation models
    )
    #v_s = Visualizer(img,scale=1.2)
    out_s = v_s.draw_instance_predictions(outputs_scratch["instances"])
    img2 = out_s.get_image()[:, :, ::-1]

    v_p = Visualizer(img[:, :, ::-1],
                   metadata=metadata_parts, 
                   scale=0.5, 
                   instance_mode=ColorMode.SEGMENTATION   # remove the colors of unsegmented pixels. This option is only available for segmentation models
    )
    #v_p = Visualizer(img,scale=1.2)
    out_p = v_p.draw_instance_predictions(outputs_parts["instances"])
    img3 = out_p.get_image()[:, :, ::-1]
    
    return img1, img2, img3, parts_list_damages

def main():
    st.set_page_config(layout="wide")
    c1, c2 = st.columns((1, 1))
    c2.markdown("<br><br><br><br><br><br><br><br><br><br><br><br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = c2.tabs(["Image of damages", "Image of scratches", "Image of parts", "Information about damages parts"])

    # Replace '20px' with your desired font size
    font_size = '20px'

    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """

    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    c1.title('Vehicle Insurance Core AI Module')

    with st.sidebar:
        image = Image.open('transparent_picture.png')
        st.image(image, width=150) #,use_column_width=True)
        page = option_menu(menu_title='Menu',
                        menu_icon="robot",
                        options=["Damage Detection"],
                        icons=["camera"],
                        default_index=0
                        )
  
    if page == "Damage Detection":
        c1.header('Car Parts Damage Detection')

        c1.write(
            """
            """
        )

        # Display the list of CSV files
        directory = "./"
        all_files = os.listdir(directory)
        # Filter files to only include JPG files
        jpg_files = [file for file in all_files if file.endswith((".jpg"))]

        # Select an image file from the list
        #selected_jpg = c1.selectbox("Select a JPG file from the list", ["None"] + jpg_files)

        uploaded_file = c1.file_uploader("Upload an image:")

        # Check if a file has been uploaded
        if uploaded_file is not None:
            # Load and display the image
            image = Image.open(uploaded_file)
            c1.image(image, width=450, caption="Uploaded image")

        #elif selected_jpg != 'None':
            #image = Image.open(selected_jpg)
            #c1.image(image, width=450, caption="Uploaded image")

        else:
            c1.write("Please upload an image.")

        if c1.button("Prediction"):
            with st.spinner("Loading..."):
                imagen1, imagen2, imagen3, partes = inference(image)
        
                c2.markdown("<br><br><br><br><br><br><br><br><br><br><br><br><br><br>", unsafe_allow_html=True)

                tab1.image(imagen1, width=450)
                tab2.image(imagen2, width=450)
                tab3.image(imagen3, width=450)
                tab4.table(partes)

try:
    main()
except Exception as e:
    st.sidebar.error(f"An error occurred: {e}")
