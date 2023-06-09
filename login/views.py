import datetime
import hashlib
import json
import os
import random
import shutil
import threading
import uuid
import xml.etree.ElementTree as ET
import mediapipe as mp
import numpy as np
from deepface import DeepFace
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
import re
# 解决 Forbidden (CSRF token missing or incorrect.)
from speech_ai import settings
from . import models
from .MyForms import *
from .fuc import findDb
from .py.Recorder import Recorder

import cv2
from mtcnn import MTCNN
from PIL import Image

from pathlib import Path

# 项目根目录
BaseDir = Path(__file__).resolve().parent.parent
BaseDir = str(BaseDir).replace('\\', '/')
# print(BaseDir)

# 存放上一张图片的人体点位置
last_pose = {}


# 姿态识别和保存为图片， 返回姿态位置
def picture(read_file, save_file=''):
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    mp_holistic = mp.solutions.holistic
    holistic = mp_holistic.Holistic(static_image_mode=True)

    image = cv2.imread(read_file)
    image_hight, image_width, _ = image.shape
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = holistic.process(image)

    pose = np.array([[res.x, res.y, res.z, res.visibility] for res in
                     results.pose_landmarks.landmark]).flatten() if results.pose_landmarks else np.zeros(33 * 4)
    # Lh = np.array([[res.x, res.y, res.z] for res in results.left_hand_landmarks.landmark]).flatten() if results.left_hand_landmarks else np.zeros(21*3)
    # Rh = np.array([[res.x, res.y, res.z] for res in results.right_hand_landmarks.landmark]).flatten() if results.right_hand_landmarks else np.zeros(21*3)

    annotated_image = image.copy()
    mp_drawing.draw_landmarks(annotated_image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                              landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style())
    mp_drawing.draw_landmarks(annotated_image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
    mp_drawing.draw_landmarks(annotated_image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
    if save_file != '':
        cv2.imwrite(save_file, cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR))

    return pose.reshape(-1, 4)


stand_pose = picture(os.path.join(settings.MEDIA_ROOT, 'pose', '1.png').replace('\\', '/'))


# 开始录制
def start_record(request):  # pass  后端录制要改成前端录制
    # obj_record.start()
    response = HttpResponse(json.dumps({"status": 1}), content_type="application/json")
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response["Access-Control-Max-Age"] = "1000"
    response["Access-Control-Allow-Headers"] = "*"
    return response


# 结束录制
def stop_record(request):  # pass  后端录制要改成前端录制
    # obj_record.stop()
    response = HttpResponse(json.dumps({"status": 1}), content_type="application/json")
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response["Access-Control-Max-Age"] = "1000"
    response["Access-Control-Allow-Headers"] = "*"
    return response


# 姿态识别 、 表情识别
# @csrf_exempt
def speech(request):
    if request.session.get('user_name', None):
        if request.method == 'POST':
            backends = ['opencv', 'ssd', 'dlib', 'mtcnn', 'retinaface', 'mediapipe']
            user = models.MyUser.objects.get(username=request.session.get('user_name'))
            time = request.POST.get('time').replace('/', '-')
            time_name = time.replace(' ', '_').replace(':', '-')
            img_time = round(float(request.POST.get('imgTime')), 2)

            user_dir = os.path.join(settings.MEDIA_ROOT, 'pose', user.id).replace('\\', '/')
            date_dir = os.path.join(user_dir, time_name).replace('\\', '/')

            img_content = request.FILES.get('speech')
            if not os.path.isdir(user_dir):
                os.makedirs(user_dir)
            if not os.path.isdir(date_dir):
                os.makedirs(date_dir)

            file_name = request.POST.get('total') + '.png'
            file_name2 = request.POST.get('total') + '_' + '1' + '.png'

            file_path = date_dir + '/' + file_name
            save_file = date_dir + '/' + file_name2

            # with open(filePath, 'wb+') as f:
            #     for chunk in imgContent.chunks():
            #         f.write(chunk)
            default_storage.save(file_path, img_content)

            if request.POST.get('total') == '1':
                flag = True
                limbs = 0
                body = 0
                last_pose[user.id] = picture(file_path, save_file)
                score = poseScore(stand_pose, last_pose[user.id])

            else:
                test = picture(file_path, save_file)
                limbs = limbsChanges(last_pose[user.id], test)
                body = bodyDeviation(last_pose[user.id], test)
                if limbs + body > 1:
                    flag = True
                else:
                    flag = False
                score = poseScore(stand_pose, test)
                last_pose[user.id] = test

            # eps = DeepFace.analyze(img_path=file_path, detector_backend=backends[5], actions=('emotion',),
            #                        enforce_detection=False)
            eps = MyExpression(file_path)

            ret = {'eps': [eps[0], float(eps[1])], 'status': True, 'tip': '成功执行'}  # eps['dominant_emotion']
            print(ret)

            pose = models.Pose.objects.create(
                uid=user.id,
                img='/media/pose/' + user.id + '/' + time_name + '/' + file_name,
                pose='/media/pose/' + user.id + '/' + time_name + '/' + file_name2,
                score=score, emotion=eps[0], emotion_prob=eps[1],
                flag=flag, limbsChanges=limbs, bodyDeviation=body,
                date=time, imgTime=img_time)
            pose.save()

            return JsonResponse(ret)
    else:
        return redirect("/login/tip/您还未登录 !/")


# 上传视频
def video(request):
    if request.method == 'POST':
        if request.session.get('user_name', None):
            user = models.MyUser.objects.get(username=request.session.get('user_name'))
            vid = request.FILES.get('video')
            videoExt = request.POST.get('videoExt')
            analyse_flag = request.POST.get('analyseFlag')
            time = request.POST.get('time').replace('/', '-')

            # 不存在则创建文件夹
            user_dir = os.path.join(settings.MEDIA_ROOT, 'pose', user.id).replace('\\', '/')
            time_name = request.POST.get('time').replace('/', '-').replace(' ', '_').replace(':', '-')
            date_dir = os.path.join(user_dir, time_name).replace('\\', '/')
            if not os.path.isdir(user_dir):
                os.makedirs(user_dir)
            if not os.path.isdir(date_dir):
                os.makedirs(date_dir)

            # 保存视频
            file_path = date_dir + '/1.' + str(videoExt)
            default_storage.save(file_path, ContentFile(vid.read()))

            # flag 为 true 进行分析
            if analyse_flag == 'true':
                # 创建音视频分析线程
                video_thread = threading.Thread(target=video_analyse, args=(file_path, date_dir, user.id, time))
                audio_thread = threading.Thread(target=audio_analyse, args=(file_path, date_dir, user.id, time))

                # print(time, type(time))

                # 启动线程
                video_thread.start()
                audio_thread.start()
                # 等待所有线程完成
                video_thread.join()
                audio_thread.join()

            elif analyse_flag == 'false':
                audio_analyse(file_path, date_dir, user.id, time)

            ret = {'tip': '分析完成', }
            return JsonResponse(ret)

        else:
            return redirect("/login/tip/您还未登录 !/")


# 音像分离
def convert_video_to_audio(file_path, date_dir):
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    import os

    # print('经过此函数1')
    file_ext = os.path.splitext(file_path)[1]
    try:
        audio = AudioSegment.from_file(file_path, file_ext[1:])
    except CouldntDecodeError:
        raise Exception(f" {file_ext} 格式不支持, 请使用 mp4, webm, flv,wav 等视频音频格式格式")
    # 转换为单声道
    audio = audio.set_channels(1)

    # 转换为采样率16kHz
    audio = audio.set_frame_rate(16000)

    # 采样位数16位
    audio = audio.set_sample_width(2)

    # 保存为wav文件
    # 设置文件名字为源文件的前缀
    filename = os.path.basename(file_path)
    filename_without_extension = os.path.splitext(filename)[0]
    new_file_path = os.path.join(date_dir, filename_without_extension + ".wav").replace("\\", "/")
    audio.export(new_file_path, format="wav")
    print('经过函数 convert_video_to_audio', new_file_path)
    return new_file_path


from .py.EGG.text_audio_emo import text_audio_emo_predict


def audio_analyse(file_path, date_dir, uid, time):
    print('音频分析及发音准确度统计')
    # 提取音频
    audio_path = convert_video_to_audio(file_path, date_dir)

    # 对象声明
    obj = text_audio_emo_predict(audio_name=audio_path)
    result = obj.total_predict()
    text_ret = json.dumps(result[0])
    audio_ret = json.dumps(result[1])

    record = Recorder(audio_name=audio_path)
    # 执行中间过渡函数
    temp = record.betweenness()
    final_result = record.evaluation_audio()
    affix_score = final_result[0]
    global xml_list
    xml_list = final_result[1]
    length = len(xml_list)

    # 存储分数
    fc_list = []
    ic_list = []
    pc_list = []
    tc_list = []
    # 解析所有的XML文件并将它们拼接起来
    content_all = ''
    for i in range(len(xml_list)):
        # 先读取发音准确度可视化，再读取分数
        # 读取可视化
        tree = ET.parse(xml_list[i])
        root = tree.getroot()
        content_all += root.find('read_chapter').find('rec_paper').find('read_chapter').get('content')
        # 读取分数
        tmp_xml = record.get_xml_score(xml_list[i])
        fc_list.append(tmp_xml['fluency_score'])
        ic_list.append(tmp_xml['integrity_score'])
        pc_list.append(tmp_xml['phone_score'])
        tc_list.append(tmp_xml['tone_score'])
    # 继续可视化操作
    # 初始化字典，用于存储每个字的perr_msg属性
    perr_msg_dict = {}
    # 遍历XML文件中的所有word元素并更新字典
    for sentence in root.findall('.//sentence'):
        for word in sentence.findall('word'):
            word_content = word.get('content')
            phone_list = word.findall('syll/phone')

            # 统计phone元素中perr_msg属性值为0的个数
            perr_msg_count = sum(1 for phone in phone_list if phone.get('perr_msg') == '0')

            # 根据perr_msg的个数生成一个嵌套字典
            if perr_msg_count == 0:
                perr_msg_dict[word_content] = {'perr_msg': 2}
            elif perr_msg_count == 1:
                perr_msg_dict[word_content] = {'perr_msg': 1}
            else:
                perr_msg_dict[word_content] = {'perr_msg': 0}
        # 根据perr_msg属性在content_all上设置不同颜色的背景
    content_colored = ''
    for char in content_all:
        if char in perr_msg_dict:
            perr_msg = perr_msg_dict[char]['perr_msg']
            if perr_msg == 0:
                content_colored += f'<span style="background-color: #b7e1cd">{char}</span>'
            elif perr_msg == 1:
                content_colored += f'<span style="background-color: #ffec8b">{char}</span>'
            elif perr_msg == 2:
                content_colored += f'<span style="background-color: #dc6c64">{char}</span>'
        else:
            content_colored += char
    # 继续对分数的操作 取两位小数等
    fc_list = [float(i) for i in fc_list]
    ic_list = [float(i) for i in ic_list]
    pc_list = [float(i) for i in pc_list]
    tc_list = [float(i) for i in tc_list]

    fluency_score = round(sum(fc_list) / length, 2)
    integrity_score = round(sum(ic_list) / length, 2)
    phone_score = round(sum(pc_list) / length, 2)
    tone_score = round(sum(tc_list) / length, 2)
    total_score = round(fluency_score * 0.4 + integrity_score * 0.1 +
                        affix_score * 0.2 + phone_score * 0.15 + tone_score * 0.15, 2)

    speech_temp = models.Speach.objects.create(
        uid=uid, date=time, total_score=total_score,
        fluency_score=fluency_score, integrity_score=integrity_score,
        phone_score=phone_score, tone_score=tone_score, affix_score=affix_score,
        video_path=file_path.replace('\\', '/').replace(BaseDir, ''), color_content=content_colored,
        textual_emotion=text_ret, phonetic_emotion=audio_ret
    )
    speech_temp.save()


import dlib
from PIL import Image
from torchvision import transforms
from torch.nn.functional import softmax

# 加载模型
import torch

# 加载已保存的模型
model_path = BaseDir + '/media/weights/Expression.pth'
model = torch.load(model_path, map_location=torch.device('cpu'))

# 设置为评估模式
model.eval()


def MyExpression(image_path):
    emotion = ['anger', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

    transform = transforms.Compose([
        transforms.Resize((48, 48)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])

    # 装载dlib的人脸检测器
    face_detector = dlib.get_frontal_face_detector()
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # 使用dlib检测人脸
    faces = face_detector(image, 1)

    if len(faces) == 0:
        return 'neutral'

    # 获取人脸区域
    x, y, w, h = faces[0].left(), faces[0].top(), faces[0].width(), faces[0].height()

    # 裁剪人脸
    cropped_face = image[y:y + h, x:x + w]

    # 将图像转换为PIL图像
    face_image = Image.fromarray(cropped_face)

    # 转换为模型所需的输入格式
    face_image_rgb = face_image.convert('RGB')
    face_tensor = transform(face_image_rgb).unsqueeze(0)

    # 使用模型进行预测
    output = model(face_tensor)

    prediction = torch.argmax(output, 1)

    # 计算置信度
    probabilities = softmax(output, dim=1)
    prob = probabilities.cpu().detach().numpy().max()

    return [emotion[prediction.item()], prob]


# 本地视频分析
def video_analyse(video_path, date_dir, uid, time):
    print('视频分析及表情姿态统计')
    video_path = video_path.replace('\\', '/')
    vid = cv2.VideoCapture(video_path)

    # 提取帧的频率
    frame_rate = vid.get(cv2.CAP_PROP_FPS)
    # 计算总帧数
    frame_count = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))

    # 计算每一帧的时间
    frame_time = 1 / frame_rate

    # 每隔几秒截取一帧
    interval = 5

    # 计算每隔 interval 秒需要截取的帧数
    frames_to_capture = int(interval / frame_time)

    print("总帧率：", frame_count, ", 帧频率：", frame_rate)

    count = 1
    for i in range(0, frame_count, frames_to_capture):
        random_frame_index = random.randint(i, i + frames_to_capture)
        vid.set(cv2.CAP_PROP_POS_FRAMES, random_frame_index)
        success, image = vid.read()

        if success:
            # cv2.imwrite(file_path, image)
            mp_drawing = mp.solutions.drawing_utils
            mp_drawing_styles = mp.solutions.drawing_styles
            mp_holistic = mp.solutions.holistic
            holistic = mp_holistic.Holistic(static_image_mode=True)

            # image = cv2.imread(file_path)
            image_height, image_width, _ = image.shape
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = holistic.process(image)
            pose = np.array([[res.x, res.y, res.z, res.visibility] for res in
                             results.pose_landmarks.landmark]).flatten() if results.pose_landmarks else np.zeros(33 * 4)
            annotated_image = image.copy()
            mp_drawing.draw_landmarks(annotated_image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                                      landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style())
            mp_drawing.draw_landmarks(annotated_image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
            mp_drawing.draw_landmarks(annotated_image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)

            if pose.any() != 0:
                # try:
                # 原始图片
                file_path = os.path.join(date_dir, "{}.jpg".format(count)).replace('\\', '/')
                cv2.imwrite(file_path, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

                # 人体关键点标记的图片
                pose_path = os.path.join(date_dir, "{}_1.jpg".format(count)).replace('\\', '/')
                cv2.imwrite(pose_path, cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR))

                # 表情识别
                # backends = ['opencv', 'ssd', 'dlib', 'mtcnn', 'retinaface', 'mediapipe']
                # eps = DeepFace.analyze(img_path=file_path, detector_backend=backends[0], actions=('emotion',))

                eps = MyExpression(file_path)
                if eps is None:
                    continue
                print(eps)

                if count == 1:
                    last_pose[uid] = pose.reshape(-1, 4)
                    limbs = 0
                    body = 0
                    flag = True
                else:
                    test = pose.reshape(-1, 4)
                    limbs = limbsChanges(last_pose[uid], test)
                    body = bodyDeviation(last_pose[uid], test)
                    if limbs + body > 1:
                        flag = True
                    else:
                        flag = False
                    last_pose[uid] = test

                img_time = round(random_frame_index * frame_time, 2)
                score = poseScore(stand_pose, pose.reshape(-1, 4))
                pose = models.Pose.objects.create(
                    uid=uid,
                    # 标记
                    img=file_path.replace('\\', '/').replace(BaseDir, ''),
                    pose=pose_path.replace('\\', '/').replace(BaseDir, ''),
                    score=score, emotion=eps[0], emotion_prob=eps[1],  # eps['dominant_emotion']
                    flag=flag, limbsChanges=limbs, bodyDeviation=body,
                    date=time, imgTime=img_time)
                pose.save()
                count += 1
                # except:
                #     print("表情识别失败")
            else:
                print("未识别到姿态")
        else:
            print('截取图像未成功')
    vid.release()


# 查分
def speachScore(request):
    if request.method == 'GET':
        uid = request.session.get('user_id')
        if uid:
            # user_name = request.session.get('user_name')
            dates = models.Speach.objects.filter(uid=uid).values('date').distinct()
            if len(dates) == 0:
                return redirect("/index/tip/请您先评测 !/")
            dates = [i['date'] for i in list(dates)]
            date = dates[-1]

            return redirect('/login/score/' + date.strftime('%Y-%m-%d_%H:%M:%S'))
        else:
            return redirect("/login/tip/您还未登录 !/")

    if request.method == 'POST':
        uid = request.session.get('user_id')
        date = request.POST.get('date')
        if uid:
            return redirect("/login/score/" + date.replace(' ', '_'))
        else:
            return redirect("/login/tip/您还未登录 !/")


# 生成综合评价性文字
def generate_feedback(tone_score, phone_score, fluency_score, affix_score, body_score, accurate_ratio):
    feedback = []

    # 发音调型反馈
    if tone_score < 80:
        feedback.append("发音调型需要改进。请加强练习，关注声调的高低起伏，确保正确地表达每个音节的声调；")
    elif tone_score < 90:
        feedback.append("发音调型较好，但仍有提升空间。继续关注声调的高低起伏，提高声调掌握程度；")
    else:
        feedback.append("发音调型非常好。保持良好的声调掌握，确保演讲内容准确传达；")

    # 发音韵律反馈
    if phone_score < 80:
        feedback.append("发音韵律方面存在问题。注意提高语速、音量和停顿的掌握，使演讲更具有吸引力；")
    elif phone_score < 90:
        feedback.append("发音韵律较好，但仍有提升空间。继续关注语速、音量和停顿的掌握，使演讲更加动听；")
    else:
        feedback.append("发音韵律非常好。保持良好的语速、音量和停顿掌握，为听众带来愉悦的听觉体验；")

    # 演讲流畅度反馈
    if fluency_score < 75:
        feedback.append("演讲流畅度有待提高。多加练习，确保在演讲过程中不出现过多的停顿；")
    elif fluency_score < 90:
        feedback.append("演讲流畅度较好，但仍有提升空间。继续练习，确保在演讲过程中流畅自如；")
    else:
        feedback.append("演讲流畅度非常好。保持流畅的表达，让听众更容易理解演讲内容；")

    # 演讲缀词冗余反馈
    if affix_score < 85:
        feedback.append("演讲中缀词和冗余表达较多。注意提高表达的简洁明了，避免使用过多的填充词；")
    elif affix_score < 90:
        feedback.append("演讲中缀词和冗余表达较少，但仍有改进空间。继续提高表达的简洁明了，减少填充词的使用；")
    else:
        feedback.append("演讲中缀词和冗余表达非常少。保持简洁明了的表达，使听众更容易理解演讲内容；")

    # 人体姿态评估反馈
    if body_score < 60:
        feedback.append("人体姿态需要改进。注意保持自然放松的站姿，保持眼神交流，以增强与听众的互动；")
    elif body_score < 80:
        feedback.append("人体姿态较好，但仍有提升空间。继续保持自然的站姿和眼神交流，提高演讲的表现力；")
    else:
        feedback.append("人体姿态非常好。保持良好的站姿和眼神交流，为听众带来愉悦的视觉体验；")

    # 发音准确性反馈
    if accurate_ratio < 0.6:
        feedback.append("发音准确性较低。请加强发音练习，提高发音准确性，确保听众能更好地理解演讲内容。")
    elif accurate_ratio < 0.8:
        feedback.append("发音准确性较好，但仍有提升空间。继续加强发音练习，进一步提高发音准确性。")
    else:
        feedback.append("发音准确性非常高。保持准确的发音，使听众更容易理解演讲内容。")

    return feedback


def speachDateScore(request, date):
    if request.method == 'GET':
        uid = request.session.get('user_id')
        user_name = request.session.get('user_name')

        # date 进行处理
        date = datetime.datetime.strptime(date, '%Y-%m-%d_%H:%M:%S')
        # print(date)

        if uid:
            exists = models.Speach.objects.filter(uid=uid, date=date).exists()

            if exists:
                dates = models.Speach.objects.filter(uid=uid).values('date').distinct()
                dates = [i['date'].strftime('%Y-%m-%d %H:%M:%S') for i in list(dates)]

                # 语音
                speech_table_value = list(models.Speach.objects.filter(uid=uid, date=date).values(
                    'content', 'fluency_score', 'integrity_score', 'phone_score', 'tone_score',
                    'affix_score', 'total_score', 'topic_score', 'color_content', 'textual_emotion',
                    'phonetic_emotion'))
                topic_score = speech_table_value[0]['topic_score']
                speech_table = [speech_table_value[0]['fluency_score'], speech_table_value[0]['integrity_score'],
                                speech_table_value[0]['phone_score'], speech_table_value[0]['tone_score'],
                                speech_table_value[0]['affix_score'], speech_table_value[0]['total_score'],
                                ]
                # 文本情感
                text_emo = json.loads(speech_table_value[0]['textual_emotion'])
                text_emotion_dict = {'negative': 0.15, 'neutral': 0.5, 'positive': 0.85}
                text_emotion = []
                for i in range(len(text_emo)):
                    if text_emo[i][0] == 'neutral':
                        text_emotion.append(
                            [text_emo[i][0], text_emotion_dict[text_emo[i][0]] + (text_emo[i][1] - 0.5) * 0.2])
                    else:
                        text_emotion.append(
                            [text_emo[i][0], text_emotion_dict[text_emo[i][0]] + (text_emo[i][1] - 0.5) * 0.15])

                # 语音情感
                audio_emo = json.loads(speech_table_value[0]['phonetic_emotion'])
                audio_emotion_dict = {'angry': 0.15, 'anger': 0.15, 'fear': 0.15, 'sad': 0.15, 'neutral': 0.5,
                                      'happy': 0.85, 'surprise': 0.85}
                audio_emotion = []
                for i in range(len(audio_emo)):
                    if audio_emo[i][0] == 'neutral':
                        audio_emotion.append(
                            [audio_emo[i][0], audio_emotion_dict[audio_emo[i][0]] + (audio_emo[i][1] - 0.5) * 0.2])
                    else:
                        audio_emotion.append(
                            [audio_emo[i][0], audio_emotion_dict[audio_emo[i][0]] + (audio_emo[i][1] - 0.5) * 0.15])

                # 发音可视化字符
                pro_viual = speech_table_value[0]['color_content']
                # 发音可视化字符串
                # 输出评价文字
                # 统计颜色个数
                # 定义三个正则表达式，分别用于匹配三种颜色
                red_pattern = re.compile(r'style="background-color: #dc6c64">(.+?)</span>')
                green_pattern = re.compile(r'style="background-color: #b7e1cd">(.+?)</span>')
                yellow_pattern = re.compile(r'style="background-color: #ffec8b">(.+?)</span>')
                # 使用正则表达式匹配字符串，并计算出现次数
                red_count = len(re.findall(red_pattern, pro_viual))
                green_count = len(re.findall(green_pattern, pro_viual))
                yellow_count = len(re.findall(yellow_pattern, pro_viual))
                # 统计评价标准
                # 音准反馈
                accurate_ratio = green_count / (green_count + red_count + yellow_count)
                # 肢体反馈/暂以total_score作为肢体评测反馈依据
                body_score = speech_table_value[0]['total_score']
                # 调型反馈
                tone_score = speech_table_value[0]['tone_score']
                # 韵律反馈
                phone_score = speech_table_value[0]['phone_score']
                # 流畅度反馈
                fluency_score = speech_table_value[0]['fluency_score']
                # 缀词反馈
                affix_score = speech_table_value[0]['affix_score']
                # 调用函数，获取反馈字符串
                feedback = generate_feedback(tone_score, phone_score, fluency_score,
                                             affix_score, body_score, accurate_ratio)

                # 是否有主题契合度评分
                topic_flag = 'false'
                if topic_score is not None:
                    speech_table.append(topic_score)
                else:
                    topic_flag = 'true'

                pose = list(models.Pose.objects.filter(uid=request.session.get('user_id'), date=date)
                            .values('score', 'imgTime', 'pose', 'flag', 'emotion',
                                    'limbsChanges', 'bodyDeviation', 'emotion_prob'
                                    ))
                pose_score = [i['score'] for i in pose]
                imgTime = [i['imgTime'] for i in pose]
                flag = [str(i['flag']) for i in pose]
                emotion = [i['emotion'] for i in pose]

                emotion_prob = [i['emotion_prob'] for i in pose]
                expression_emotion_dict = {'angry': 0.15, 'anger': 0.15, 'fear': 0.15, 'sad': 0.15, 'disgust': 0.15,
                                           'neutral': 0.5,
                                           'happy': 0.85, 'surprise': 0.85}
                expression_emotion = []
                for i in range(len(emotion)):
                    if emotion[i] == 'neutral':
                        expression_emotion.append(
                            [emotion[i], expression_emotion_dict[emotion[i]] + (emotion_prob[i] - 0.5) * 0.2])
                    else:
                        expression_emotion.append(
                            [emotion[i], expression_emotion_dict[emotion[i]] + (emotion_prob[i] - 0.5) * 0.15])

                dt = {'score': pose_score, 'imgTime': imgTime, 'emotion': emotion, 'flag': flag,
                      'expression_emotion': expression_emotion, 'text_emotion': text_emotion,
                      'audio_emotion': audio_emotion}

                limbs = sum([i['limbsChanges'] for i in pose])
                body = sum([i['bodyDeviation'] for i in pose])

                # pose 图片 flag 为 1 是否超过一定数量，没超过则全部显示
                count_flag = False
                if flag.count('True') > 10:
                    count_flag = True
                    pass
                # 返回
                return render(request, 'score/score.html',
                              {'login_status': True, 'user_name': user_name,
                               'date': date.strftime('%Y-%m-%d %H:%M:%S'), 'data': dt, 'speech_score': speech_table,
                               'content': speech_table, 'pose': pose, 'count_flag': count_flag,
                               'topic_flag': topic_flag, 'dates': dates, 'limbs': limbs, 'body': body,
                               'pro_viual': pro_viual, 'feedback': feedback
                               })  # pro_viual是音准可视化字符串，feedback是生成的反馈字符串
            else:
                return HttpResponse('<h1>该时间您下并没有进行评测 !</h1>')

        else:
            return redirect("/login/tip/您还未登录 !/")


# 展示 头像
# def show_avatar(request):
#     if request.session.get('user_name'):
#         user = models.MyUser.objects.get(username=request.session.get('user_name'))
#         avatar = user.avatar
#         # user = models.Avatar.objects.filter(name='trent')[0]
#         # avatarName = str(user.avatar)
#         # avatarUrl = '%s/users/%s' % (settings.MEDIA_URL, avatarName) # 另一种写法
#         # if request.method == 'GET':
#         #     users = models.MyUser.objects.all()
#         #     return render(request, 'login/show.html', {'avatar': avatar})
#         return render(request, 'login/show.html', {'avatar': avatar, 'username': user.username})
#         # avatar = os.path.join(settings.MEDIA_URL, 'photos/demo.png')
#         # avatar_info = {'userName':str(image.user), 'avatarUrl': avatarUrl}
#         # return render(request, 'login/show.html', {'avatar':avatar})
#     else:
#         return redirect("/login/tip/您还未登录 !/")


# 上传头像
# def upload_avatar(request):
#     if request.method == 'POST':
#         if request.session.get('user_name', None):
#             # image = models.MyUser(
#             #     username = request.session.get('user_name'),
#             #     avatar=request.FILES.get('avatar'),
#             #     # face=request.FILES.get('face')
#             # )
#             user = models.MyUser.objects.get(username=request.session.get('user_name'))
#             dire = os.path.join(settings.MEDIA_ROOT, 'avatar')
#             img = request.FILES.get('avatar')
#             fileName = user.id + '.' + img.name.split('.')[-1]
#             filePath = os.path.join(dire, fileName).replace('\\', '/')
#             # user.avatar.delete()
#             if not os.path.isdir(dire):
#                 os.mkdir(dire)
#             if os.path.exists(filePath):
#                 os.remove(filePath)
#             with open(filePath, 'wb+') as f:
#                 for chunk in img.chunks():
#                     f.write(chunk)
#             user.avatar = 'avatar' + '/' + fileName
#             user.save()
#             # models.MyUser.objects.filter(id=user.id).update(avatar = 'avatar' + '/'+ fileName)
#             return HttpResponse('<h1>' + request.session.get('user_name') + '</h1>')
#         else:
#             # return redirect('/login')
#             return HttpResponse('<h1>user_name为空!</h1>')
#
#     else:
#         return render(request, 'login/upload_image.html')


# 用户信息
def user_info(request):
    if request.method == 'GET':
        if request.session.get('is_login', None):
            user = models.MyUser.objects.get(username=request.session.get('user_name'))
            return render(request, 'user/info.html', {'user': user, 'login_status': True, 'user_name': user.username})
        return redirect("/login/tip/您还未登录 !/")

    # if request.method == 'POST':
    #     # 获取当前登录用户才能修改信息
    #     user = models.MyUser.objects.get(username=request.user.username)
    #     data = request.POST
    #     # print(request.FILES)
    #     avatar = request.FILES.get('avatar')
    #     # print(avatar)
    #     username = data.get("username")
    #     email = data.get("email")
    #     phone = data.get('phone')
    #     address = data.get('address')
    #     cate = data.get('cate')
    #     detail = data.get('detail')
    #     # 判断用户修改信息时，有没有上传新图片
    #     # 上传了换头像链接 否则不换
    #     # 无该判断时，若用户未更换图片，则原图片链接会被赋空值，导致头像丢失
    #     if avatar:
    #         u.avatar = avatar
    #     u.username = username
    #     u.email = email
    #     u.phone = phone
    #     u.address = address
    #     u.cate = cate
    #     u.detail = detail
    #     # 可能抛出异常：
    #     # 如果该用户修改的昵称已存在数据库中，会报错
    #     # 原因是，在我的设置里。用户名称是惟一的，不可重复的
    #     # 因此，避免bug，且提供给用户弹窗警告
    #     try:
    #         # 如果未获取当前用户，save会新建一个没有密码的用户，操作是错误的
    #         u.save()
    #     except:
    #         info = "该用户名已被注册"
    #         return render(request,'Myapp/error.html', {'info':info})
    #     # 和查看用户信息同理，每个用户都有自己的路由，修改后，重定向到新的路由
    #     # 因为该路由由用户名决定
    #     return HttpResponseRedirect('/profile/%s' % userinfo.username)
    # else:
    #     return render(request, 'Myapp/profile_edit.html', {'userinfo':userinfo})


# 求角度
def GetAngle(c1p1, c1p2, c2p1, c2p2):
    # 求出斜率
    if c1p2[0] == c1p1[0]:
        x = np.array([0, 1])
    else:
        k1 = (c1p2[1] - c1p1[1]) / (float(c1p2[0] - c1p1[0]))
        x = np.array([1, k1])
    if c2p2[0] == c2p1[0]:
        y = np.array([0, 1])
    else:
        k2 = (c2p2[1] - c2p1[1]) / (float(c2p2[0] - c2p1[0]))
        y = np.array([1, k2])
    # 模长
    Lx = np.sqrt(x.dot(x))
    Ly = np.sqrt(y.dot(y))
    # 根据向量之间求其夹角并保留固定小数位数
    Cobb = (np.arccos(x.dot(y) / (float(Lx * Ly))) * 180 / np.pi)
    return round(Cobb, 3)


# 前后图片变化程度， True代表变化大， False代表变化小

def limbsChanges(sta, test):
    scope = 60
    flag_lst = [(11, 13), (13, 15), (12, 14), (14, 16), (24, 26), (26, 28), (23, 25), (25, 27)]
    for key in flag_lst:
        angle = GetAngle(sta[key[0]], sta[key[1]], test[key[0]], test[key[1]])
        # 四肢变化大 或者 人体偏移程度大
        if angle >= scope:
            return 1
    return 0


# 计算前后图片 人体偏移程度
def bodyDeviation(sta, test):
    # mediapipe中坐标是已经归一化后的，可以直接进行计算
    sta2 = []
    test2 = []
    for i in range(0, 33):
        # 置信度大于0.99
        if sta[i][3] > 0.99 and test[i][3] > 0.99:
            sta2.append([sta[i][0], sta[i][1]])
            test2.append([test[i][0], test[i][1]])
    sta2 = np.array(sta2)
    test2 = np.array(test2)

    # 计算距离
    A = np.array([sta2[:, 0].mean(), sta2[:, 1].mean()])
    B = np.array([test2[:, 0].mean(), test2[:, 1].mean()])
    dist = np.sqrt(sum(np.power((A - B), 2)))

    # 距离范围
    if dist > 0.3:
        return 1
    return 0


# 站姿正 得分
def poseScore(sta, test):
    scope = 20
    score = 0
    score_lst = [11, 12, 23, 24, 27, 28]
    for key in score_lst:
        angle = GetAngle(sta[key], sta[0], test[key], test[0])
        if abs(angle - scope) > scope:
            score += 0
        else:
            score += abs(angle - scope) / scope

    total_score = score / len(score_lst) * 100
    return round(total_score, 2)


# 上传 人脸图片
def face_upload(request):
    if request.session.get('is_login', None):
        if request.method == 'GET':
            user_name = request.session.get('user_name')
            return render(request, 'face/upload.html', {'login_status': True, 'user_name': user_name, 'page': 'upload'})

        if request.method == 'POST':
            user = models.MyUser.objects.get(username=request.session.get('user_name'))
            dirFace = os.path.join(settings.MEDIA_ROOT, 'face', user.id).replace('\\', '/')
            imgs = request.FILES.getlist('face')

            if os.path.isdir(dirFace):
                # 如果目标路径存在原文件夹的话就先删除
                shutil.rmtree(dirFace)

            os.makedirs(dirFace)

            for img in imgs:
                # 后缀名
                # fileName = str(uuid.uuid4()).replace('-', '') + '.' + img.name.split('.')[-1]
                file_name = str(uuid.uuid4()).replace('-', '') + '.png'
                filePath = os.path.join(dirFace, file_name).replace('\\', '/')
                with open(filePath, 'wb+') as f:
                    for chunk in img.chunks():
                        f.write(chunk)

            if os.path.exists('./media/face/representations_vgg_face.pkl'):
                os.remove('./media/face/representations_vgg_face.pkl')
            findDb.findDb(db_path='./media/face', enforce_detection=False, distance_metric='euclidean')

            ret = {'status': True}
            return JsonResponse(ret)

    else:
        return redirect("/login/tip/您还未登录 !/")
        # return redirect('/login')


# 人脸登录
def face_login(request):
    if request.session.get('is_login', None):
        return redirect("/index/tip/您已登录 !/")

    else:
        if request.method == 'GET':
            return render(request, 'face/face_login.html', {'page': 'login'})

        if request.method == 'POST':
            dr = os.path.join(settings.MEDIA_ROOT, 'temp').replace('\\', '/')
            model_name = ['VGG-Face', 'Facenet', 'OpenFace', 'DeepFace', 'DeepID', 'Dlib', 'Ensemble']
            img = request.FILES.get('face')
            fileName = str(uuid.uuid4()).replace('-', '') + '.png'
            filePath = os.path.join(dr, fileName).replace('\\', '/')
            with open(filePath, 'wb+') as f:
                for chunk in img.chunks():
                    f.write(chunk)
            df = DeepFace.find(img_path=filePath, model_name=model_name[0], db_path='./media/face',
                               enforce_detection=False, distance_metric='euclidean')

            os.remove(filePath)

            if df.iloc[0]['VGG-Face_euclidean'] < 0.35:
                uid = df.iloc[0]['identity'].replace('\\', '/').split('/')[-2]
                if models.MyUser.objects.get(id=uid):
                    user = models.MyUser.objects.get(id=uid)
                    request.session['is_login'] = True
                    request.session['user_id'] = user.id
                    request.session['user_name'] = user.username
                    request.session['status_flag'] = user.status_flag

                    ret = {'state': True, 'user_name': str(user.username)}
                    return JsonResponse(ret)

                else:
                    ret = {'state': False}
                    return JsonResponse(ret)

            else:
                ret = {'state': False}
                return JsonResponse(ret)


# 登录 邮箱、用户名、密码、验证码
def login(request):
    if request.session.get('is_login', None):
        return redirect("/index/tip/您已登录/")

    elif request.method == "GET":
        print(request.session.get('is_login'))
        register_form = RegisterForm()
        login_form = LoginForm()
        login_message = ""
        return render(request, 'login/login.html',
                      {'login': True, 'login_form': login_form, 'register_form': register_form,
                       'login_message': login_message})

    elif request.method == "POST":
        register_form = RegisterForm()
        login_form = LoginForm(request.POST)
        login_message = "表单验证失败"
        if login_form.is_valid():
            username = login_form.cleaned_data['username']
            password = login_form.cleaned_data['password']
            flag = login_form.cleaned_data['flag']

            if models.MyUser.objects.filter(username=username).exists():
                user = models.MyUser.objects.get(username=username)

                if user.status_flag == flag:
                    if user.password == hash_code(password):
                        request.session['is_login'] = True
                        request.session['user_id'] = user.id
                        request.session['user_name'] = user.username
                        request.session['status_flag'] = user.status_flag

                        # 普通用户
                        if user.status_flag == '0':
                            return redirect("/index/")
                        # 裁判
                        elif user.status_flag == '1':
                            return redirect("/judge/video/")
                        # 管理员
                        elif user.status_flag == '2':
                            return redirect("/Administrator/secure/index")
                    #     /Administrator/secure/index

                    else:
                        login_message = "密码不正确"
                else:
                    login_message = "请选择正确的用户身份"
            else:
                login_message = "用户不存在"
        # return render(request, 'login/login.html', locals())
        return render(request, 'login/login.html',
                      {'login': True, 'login_form': login_form, 'register_form': register_form,
                       'login_message': login_message})


# 登录 提示
def login_tip(request, tip):
    if request.method == "GET":
        register_form = RegisterForm()
        login_form = LoginForm()
        return render(request, 'login/login.html',
                      {'login': True, 'login_form': login_form, 'register_form': register_form,
                       'login_message': None, 'tip': tip})


# 注册 邮箱、用户名、密码、验证码
def register(request):
    if request.session.get('is_login', None):
        return redirect("/index/tip/您已登录/")

    elif request.method == "GET":
        register_form = RegisterForm()
        login_form = LoginForm()
        login_message = ""
        return render(request, 'login/login.html',
                      {'login': False, 'login_form': login_form, 'register_form': register_form,
                       'login_message': login_message})

    elif request.method == "POST":
        login_form = LoginForm()
        register_form = RegisterForm(request.POST)
        register_message = "表单验证失败"
        if register_form.is_valid():
            email = register_form.cleaned_data['email']
            username = register_form.cleaned_data['username']
            password = register_form.cleaned_data['password']
            password2 = register_form.cleaned_data['password2']
            if password != password2:
                register_message = '两次密码不一样'
                return render(request, 'login/login.html',
                              {'login': False, 'register_form': register_form, 'login_form': login_form,
                               'register_message': register_message})

            elif models.MyUser.objects.filter(email=email).exists():
                register_message = '邮箱已注册'
                return render(request, 'login/login.html',
                              {'login': False, 'register_form': register_form, 'login_form': login_form,
                               'register_message': register_message})

            elif models.MyUser.objects.filter(username=username).exists():
                register_message = '用户名已注册'
                return render(request, 'login/login.html',
                              {'login': False, 'register_form': register_form, 'login_form': login_form,
                               'register_message': register_message})
            else:
                user = models.MyUser.objects.create(username=username, email=email, password=hash_code(password))
                user.save()
                request.session['is_login'] = True
                request.session['user_id'] = user.id
                request.session['user_name'] = user.username
                # return redirect("/index", login_status=True)
                return redirect("/index/")
                # return render(request, "index.html", {'login_status': True, 'user_name': str(user.username)})

        return render(request, 'login/login.html',
                      {'login': False, 'register_form': register_form, 'login_form': login_form,
                       'register_message': register_message})


# 注销
def logout(request):
    if not request.session.get('is_login', None):
        return redirect("/login/tip/您还未登录 !")

    request.session.flush()
    return redirect("/login")


# 字符串+哈希
def hash_code(s, salt='speech_ai'):  # 加点盐
    h = hashlib.sha256()
    s += salt
    h.update(s.encode())  # update方法只接收bytes类型
    return h.hexdigest()


# 返回登录注册页面
def login_register(request):
    if request.session.get('is_login', None):
        return redirect("/index/tip/您已登录/")

    elif request.method == "GET":
        login_form = LoginForm()
        register_form = RegisterForm()
        return render(request, 'login/login.html',
                      {'login': True, 'login_form': login_form, 'register_form': register_form})


# 返回 404 页面
def page_not_found(request, exception):
    if request.session.get('is_login', None):
        user_name = request.session.get('user_name')
        return render(request, '404.html', {'login_status': True, 'user_name': user_name})
    return render(request, '404.html', {'login_status': False})

# 500
# def page_error(request, exception):
#     return render(request, '404.html')
