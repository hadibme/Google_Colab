"""
اسکریپت سامانه جامع اطلاعات مشتریان بانکی ایران

این اسکریپت یک رابط کاربری تعاملی برای جستجوی اطلاعات مشتریان در پایگاه‌های داده بانک‌های ملی، ملت و صادرات فراهم می‌کند.
ویژگی‌های اصلی شامل انتخاب بانک، جستجوی اطلاعات بر اساس فیلترهای مختلف، حذف داده‌های تکراری، ادغام رکوردها و تولید گزارش PDF با پشتیبانی از زبان فارسی است.

وابستگی‌ها:
- duckdb: برای مدیریت پایگاه داده
- pandas: برای پردازش داده‌ها
- fpdf: برای تولید فایل‌های PDF
- gdown: برای دانلود فایل‌ها از Google Drive
- arabic_reshaper و python-bidi: برای پشتیبانی از متن فارسی
- ipywidgets: برای ایجاد رابط کاربری تعاملی

توابع اصلی:
- format_persian: قالب‌بندی متن فارسی برای نمایش صحیح
- clean_duplicate_data: حذف رکوردهای تکراری و ادغام داده‌ها
- create_melli_pdf, create_mellat_pdf, create_saderat_pdf: تولید گزارش PDF برای هر بانک
- download_file: دانلود فایل‌های پایگاه داده و لوگوها
- on_bank_change, display_search_form, on_search_clicked, on_pdf_button_clicked: مدیریت رابط کاربری و فرآیند جستجو

ویژگی‌ها:
- پشتیبانی از جستجوی چندمعیاره (نام، کد ملی، شماره کارت و غیره)
- حذف هوشمند داده‌های تکراری بر اساس منطق خاص هر بانک
- تولید گزارش PDF با قالب‌بندی فارسی و لوگوی بانک
- رابط کاربری تعاملی با استفاده از ویجت‌های Jupyter

تنظیمات:
- پایگاه‌های داده بانک‌ها به‌صورت فایل DuckDB از Google Drive دانلود می‌شوند
- فونت‌های IRANSans و لوگوهای بانک‌ها برای گزارش‌دهی استفاده می‌شوند

نحوه استفاده:
1. بانک مورد نظر را از منوی کشویی انتخاب کنید
2. فیلترهای جستجو را در فرم مربوطه وارد کنید
3. روی دکمه "شروع جستجو" کلیک کنید
4. نتایج نمایش داده شده و امکان دانلود گزارش PDF فراهم می‌شود

ملاحظات:
- حداقل یک فیلد جستجو باید پر شود
- برای بانک‌های ملی و ملت، جستجوی کد ملی و سال تولد با شرایط خاص مدیریت می‌شود
- داده‌های تکراری بر اساس کد ملی (برای ملی و ملت) یا نام کامل (برای صادرات) حذف می‌شوند
"""

# coding: utf-8

# نصب کتابخانه‌های مورد نیاز
!pip install duckdb fpdf gdown arabic-reshaper python-bidi -q

# وارد کردن کتابخانه‌ها
import ipywidgets as widgets
from IPython.display import display, clear_output, HTML
import gdown
import os
import duckdb
import pandas as pd
import time
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import base64
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="fpdf.ttfonts")

# تنظیمات اولیه
os.environ['DUCKDB_DISABLE_EXTENSION_LOADING'] = '1'

# متغیرهای سراسری
current_db = None
current_bank = None
search_results = None
bank_databases = {
    "ملی": {"id": "13h51E-6S_FVB3wPMRVFMv6POmykvytli", "file": "Melli.duckdb"},
    "ملت": {"id": "1JCJEQU6dAFtjF64UoeBix76drj0ktPSV", "file": "Mellat.duckdb"},
    "صادرات": {"id": "17sU_vh2y8HPc2zOatww1LSc1lr2NR-PD", "file": "Saderat.duckdb"}
}

# توابع کمکی برای متن فارسی
def format_persian(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def create_download_link(pdf_data, filename):
    b64 = base64.b64encode(pdf_data).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{filename}">دانلود فایل PDF</a>'

# تابع جدید برای پاک‌سازی داده‌های تکراری بر اساس منطق مشخص
def clean_duplicate_data(df, bank_name):
    """
    حذف رکوردهای تکراری بر اساس منطق مشخص شده
    """
    if bank_name == "صادرات":
        # برای بانک صادرات از نام و نام خانوادگی استفاده می‌کنیم
        group_key = "FullName"
    else:
        # برای بانک‌های ملی و ملت از کد ملی استفاده می‌کنیم
        group_key = "NATIONAL_CODE" if bank_name == "ملی" else "NATIONAL_CODE"

    # تبدیل "None" به None واقعی برای پردازش بهتر
    df = df.replace("None", None)
    
    cleaned_data = []
    
    # گروه‌بندی رکوردها بر اساس کلید اصلی
    grouped = df.groupby(group_key, dropna=False)
    
    for _, group in grouped:
        if len(group) == 1:
            cleaned_data.append(group.iloc[0])
            continue
        
        # مرحله 1: حذف رکوردهای کاملاً تکراری
        unique_records = group.drop_duplicates()
        
        if len(unique_records) == 1:
            cleaned_data.append(unique_records.iloc[0])
            continue
        
        # مرحله 2 و 3: پردازش رکوردهای با اطلاعات مکمل
        records_to_keep = []
        
        for i, record in unique_records.iterrows():
            is_duplicate = False
            
            for j, other_record in unique_records.iterrows():
                if i == j:
                    continue
                
                # بررسی کامل‌تر بودن رکورد دیگر
                is_other_better = True
                is_current_better = True
                has_real_difference = False
                
                for col in unique_records.columns:
                    if col == group_key:
                        continue
                    
                    # بررسی تفاوت‌های واقعی (مرحله 4)
                    if record[col] != other_record[col] and record[col] is not None and other_record[col] is not None:
                        has_real_difference = True
                        break
                    
                    # بررسی کامل‌تر بودن
                    if record[col] is None and other_record[col] is not None:
                        is_current_better = False
                    
                    if other_record[col] is None and record[col] is not None:
                        is_other_better = False
                
                if has_real_difference:
                    continue
                
                if is_other_better and not is_current_better:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                records_to_keep.append(record)
        
        # اضافه کردن رکوردهای منحصر به فرد به داده‌های پاک‌سازی شده
        for record in records_to_keep:
            cleaned_data.append(record)
    
    # ایجاد DataFrame جدید از داده‌های پاک‌سازی شده
    cleaned_df = pd.DataFrame(cleaned_data)
    
    # تبدیل None به "None" برای نمایش بهتر
    cleaned_df = cleaned_df.fillna("None")
    
    return cleaned_df

# تابع ایجاد PDF برای بانک ملی
def create_melli_pdf(data, search_params):
    # پاک‌سازی داده‌ها قبل از ایجاد PDF
    cleaned_data = clean_duplicate_data(data, "ملی")
    
    # ادغام رکوردهای با کد ملی یکسان
    merged_records = []
    grouped = cleaned_data.groupby('NATIONAL_CODE', dropna=False)
    
    for national_code, group in grouped:
        if len(group) == 1:
            merged_records.append(group.iloc[0].to_dict())
            continue
        
        # ایجاد رکورد ادغام شده
        merged_record = {}
        counter = {}
        
        for _, record in group.iterrows():
            for col, value in record.items():
                if value == "None":
                    continue
                    
                if col not in merged_record:
                    merged_record[col] = value
                elif merged_record[col] != value:
                    # اگر مقدار متفاوت است، شماره‌گذاری کنیم
                    if col not in counter:
                        counter[col] = 1
                    counter[col] += 1
                    new_col = f"{col}_{counter[col]}"
                    merged_record[new_col] = value
        
        merged_records.append(merged_record)
    
    merged_df = pd.DataFrame(merged_records).fillna("None")

    pdf = FPDF()
    pdf.add_page()
    
    # اضافه کردن فونت‌ها
    pdf.add_font('IRANSans', '', 'IRANSansWeb_Medium.ttf', uni=True)
    pdf.add_font('IRANSansB', '', 'IRANSansWeb_Bold.ttf', uni=True)
    
    # اضافه کردن لوگو در بالای صفحه
    if os.path.exists('melli_logo.png'):
        pdf.image('melli_logo.png', x=70, y=10, w=60)
    
    # ایجاد فاصله عمودی زیاد بعد از لوگو
    pdf.ln(90)
    
    # عنوان اصلی با فونت Bold و چند خطی
    pdf.set_font('IRANSansB', '', 14)
    title = format_persian(f"اطلاعات یافت شده در دیتابیس بانک ملی")
    pdf.cell(0, 10, title, 0, 1, 'C')
    
    subtitle = format_persian(f"برای \"{', '.join(search_params)}\"")
    pdf.cell(0, 10, subtitle, 0, 1, 'C')
    
    footer_title = format_persian("(پس از حذف تکراری‌ها و ادغام رکوردها)")
    pdf.cell(0, 10, footer_title, 0, 1, 'C')
    
    pdf.ln(15)
    
    # محتوای داده‌ها با راست‌چینی و فونت Medium
    pdf.set_font('IRANSans', '', 12)
    for i, record in enumerate(merged_df.to_dict('records'), start=1):
        # تبدیل نام ستون‌ها به فارسی
        col_names = {
            'FULL_NAME': 'نام و نام خانوادگی',
            'BIRTH_DATE': 'تاریخ تولد',
            'NATIONAL_CODE': 'کد ملی',
            'CARD_NO': 'شماره کارت',
            'MOBILE': 'شماره همراه'
        }
        
        text_lines = [f"{i}."]
        
        # اطلاعات اصلی (همیشه نمایش داده می‌شوند اگر وجود داشته باشند)
        for col in ['FULL_NAME', 'BIRTH_DATE', 'NATIONAL_CODE', 'MOBILE']:
            if col in record and record[col] != "None":
                text_lines.append(f"{col_names[col]}: {record[col]}")
        
        # پردازش شماره کارت‌ها (ممکن است چندین شماره کارت وجود داشته باشد)
        card_numbers = []
        for key, value in record.items():
            if key.startswith('CARD_NO') and value != "None":
                if key == 'CARD_NO':
                    card_numbers.append(f"شماره کارت: {value}")
                else:
                    num = key.split('_')[-1]
                    card_numbers.append(f"شماره کارت {num}: {value}")
        
        if card_numbers:
            text_lines.extend(card_numbers)
        
        # ترکیب تمام خطوط متن
        full_text = format_persian("\n".join(text_lines))
        pdf.multi_cell(0, 7, full_text, align='R')
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin1')

# تابع ایجاد PDF برای بانک ملت
def create_mellat_pdf(data, search_params):
    # پاک‌سازی داده‌ها قبل از ایجاد PDF
    cleaned_data = clean_duplicate_data(data, "ملت")
    
    # ادغام رکوردهای با کد ملی یکسان
    merged_records = []
    grouped = cleaned_data.groupby('NATIONAL_CODE', dropna=False)
    
    for national_code, group in grouped:
        if len(group) == 1:
            merged_records.append(group.iloc[0].to_dict())
            continue
        
        # ایجاد رکورد ادغام شده
        merged_record = {}
        counter = {}
        
        for _, record in group.iterrows():
            for col, value in record.items():
                if value == "None":
                    continue
                    
                if col not in merged_record:
                    merged_record[col] = value
                elif merged_record[col] != value:
                    # اگر مقدار متفاوت است، شماره‌گذاری کنیم
                    if col not in counter:
                        counter[col] = 1
                    counter[col] += 1
                    new_col = f"{col}_{counter[col]}"
                    merged_record[new_col] = value
        
        merged_records.append(merged_record)
    
    merged_df = pd.DataFrame(merged_records).fillna("None")

    pdf = FPDF()
    pdf.add_page()
    
    # اضافه کردن فونت‌ها
    pdf.add_font('IRANSans', '', 'IRANSansWeb_Medium.ttf', uni=True)
    pdf.add_font('IRANSansB', '', 'IRANSansWeb_Bold.ttf', uni=True)
    
    # اضافه کردن لوگو در بالای صفحه
    if os.path.exists('mellat_logo.png'):
        pdf.image('mellat_logo.png', x=70, y=10, w=60)
    
    # ایجاد فاصله عمودی زیاد بعد از لوگو
    pdf.ln(75)
    
    # عنوان اصلی با فونت Bold و چند خطی
    pdf.set_font('IRANSansB', '', 14)
    title = format_persian(f"اطلاعات یافت شده در دیتابیس بانک ملت")
    pdf.cell(0, 10, title, 0, 1, 'C')
    
    subtitle = format_persian(f"برای \"{', '.join(search_params)}\"")
    pdf.cell(0, 10, subtitle, 0, 1, 'C')
    
    footer_title = format_persian("(پس از حذف تکراری‌ها و ادغام رکوردها)")
    pdf.cell(0, 10, footer_title, 0, 1, 'C')
    
    pdf.ln(15)
    
    # محتوای داده‌ها با راست‌چینی و فونت Medium
    pdf.set_font('IRANSans', '', 12)
    for i, record in enumerate(merged_df.to_dict('records'), start=1):
        # تبدیل نام ستون‌ها به فارسی
        col_names = {
            'FULL_NAME': 'نام و نام خانوادگی',
            'BIRTH_DATE': 'تاریخ تولد',
            'FATHER_NAME': 'نام پدر',
            'NATIONAL_CODE': 'کد ملی',
            'ID_NUMBER': 'شماره شناسنامه',
            'MOBILE': 'شماره همراه',
            'CARD_NO': 'شماره کارت',
            'ACCOUNT_NUMBER': 'شماره حساب',
            'PROVINCE_NAME': 'استان',
            'CITY_NAME': 'شهر',
            'BIRTH_PROVINCE': 'استان محل تولد',
            'BIRTH_CITY': 'شهر محل تولد',
            'ADDRESS': 'نشانی'
        }
        
        text_lines = [f"{i}."]
        
        # اطلاعات اصلی (همیشه نمایش داده می‌شوند اگر وجود داشته باشند)
        for col in ['FULL_NAME', 'BIRTH_DATE', 'FATHER_NAME', 'NATIONAL_CODE', 'ID_NUMBER', 'MOBILE']:
            if col in record and record[col] != "None":
                text_lines.append(f"{col_names[col]}: {record[col]}")
        
        # پردازش شماره کارت‌ها (ممکن است چندین شماره کارت وجود داشته باشد)
        card_numbers = []
        for key, value in record.items():
            if key.startswith('CARD_NO') and value != "None":
                if key == 'CARD_NO':
                    card_numbers.append(f"شماره کارت: {value}")
                else:
                    num = key.split('_')[-1]
                    card_numbers.append(f"شماره کارت {num}: {value}")
        
        if card_numbers:
            text_lines.extend(card_numbers)
        
        # اطلاعات حساب و سایر اطلاعات
        for col in ['ACCOUNT_NUMBER', 'PROVINCE_NAME', 'CITY_NAME', 'BIRTH_PROVINCE', 'BIRTH_CITY', 'ADDRESS']:
            if col in record and record[col] != "None":
                text_lines.append(f"{col_names[col]}: {record[col]}")
        
        # ترکیب تمام خطوط متن
        full_text = format_persian("\n".join(text_lines))
        pdf.multi_cell(0, 7, full_text, align='R')
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin1')

# تابع ایجاد PDF برای بانک صادرات
def create_saderat_pdf(data, search_params):
    # پاک‌سازی داده‌ها قبل از ایجاد PDF
    cleaned_data = clean_duplicate_data(data, "صادرات")

    pdf = FPDF()
    pdf.add_page()
    
    # اضافه کردن فونت‌ها
    pdf.add_font('IRANSans', '', 'IRANSansWeb_Medium.ttf', uni=True)
    pdf.add_font('IRANSansB', '', 'IRANSansWeb_Bold.ttf', uni=True)
    
    # اضافه کردن لوگو در بالای صفحه
    if os.path.exists('saderat_logo.png'):
        pdf.image('saderat_logo.png', x=70, y=10, w=60)
    
    # ایجاد فاصله عمودی زیاد بعد از لوگو
    pdf.ln(65)
    
    # عنوان اصلی با فونت Bold و چند خطی
    pdf.set_font('IRANSansB', '', 14)
    title = format_persian(f"اطلاعات یافت شده در دیتابیس بانک صادرات")
    pdf.cell(0, 10, title, 0, 1, 'C')
    
    subtitle = format_persian(f"برای \"{', '.join(search_params)}\"")
    pdf.cell(0, 10, subtitle, 0, 1, 'C')
    
    footer_title = format_persian("(پس از حذف تکراری‌ها)")
    pdf.cell(0, 10, footer_title, 0, 1, 'C')
    
    pdf.ln(20)
    
    # محتوای داده‌ها با راست‌چینی و فونت Medium
    pdf.set_font('IRANSans', '', 12)
    for i, row in enumerate(cleaned_data.itertuples(), start=1):
        text = format_persian(
            f"{i}. نام و نام خانوادگی: {row.FullName}\n"
            f"شماره همراه: {row.user_phone_number}\n"
            f"شماره کارت: {row.CardNumber}\n"
            f"شماره حساب: {row.AccountNumber}\n"
            f"شناسه شعبه: {row.ID_Branch}\n"
            f"نشانی ایمیل کاربر: {row.user_email_address}\n"
            f"عضویت: {row.Member}\n"
            f"شماره شناسایی قدیمی: {row.DefineNum_Old}\n"
            f"شماره شناسایی: {row.DefineationNumber}\n"
            f"نام کاربری: {row.Username}\n"
            f"رمز عبور: {row.Passw}\n"
            f"راهنمای رمز عبور: {row.Password_Hint}"
        )
        pdf.multi_cell(0, 7, text, align='R')
        pdf.ln(12)

    return pdf.output(dest='S').encode('latin1')

# تابع دانلود فایل
def download_file(file_id, file_name):
    url = f'https://drive.google.com/uc?id={file_id}'
    gdown.download(url, file_name, quiet=True)

# تابع مدیریت تغییر بانک
def on_bank_change(change):
    global current_db, current_bank
    if change['new'] == "تعیین نشده!":
        clear_output(wait=True)
        display(welcome_html)
        display(bank_dropdown)
        return

    bank_name = change['new']
    clear_output(wait=True)
    display(welcome_html)
    display(bank_dropdown)

    # پاک کردن دیتابیس قبلی
    if current_bank and current_bank != bank_name:
        if current_db:
            current_db.close()
        current_db = None

    # دانلود دیتابیس جدید
    file_info = bank_databases[bank_name]
    if not os.path.exists(file_info["file"]):
        download_file(file_info["id"], file_info["file"])

    # اتصال به دیتابیس
    current_db = duckdb.connect(database=file_info["file"], read_only=True)
    current_bank = bank_name

    # نمایش فرم جستجو
    display_search_form(bank_name)

# تابع نمایش فرم جستجو
def display_search_form(bank_name):
    global search_form
    clear_output(wait=True)
    display(welcome_html)
    display(bank_dropdown)

    # ایجاد فیلدهای جستجو بر اساس بانک
    fields = []

    if bank_name == "ملی":
        fields = [
            widgets.Text(description='نام و نام خانوادگی:', style={'description_width': 'initial'}),
            widgets.Text(description='تاریخ تولد (YYYY-MM-DD):', style={'description_width': 'initial'}),
            widgets.Text(description='شماره همراه:', style={'description_width': 'initial'}),
            widgets.Text(description='کد ملی:', style={'description_width': 'initial'}),
            widgets.Text(description='شماره کارت:', style={'description_width': 'initial'})
        ]
    elif bank_name == "ملت":
        fields = [
            widgets.Text(description='نام و نام خانوادگی:', style={'description_width': 'initial'}),
            widgets.Text(description='تاریخ تولد (YYYY-MM-DD):', style={'description_width': 'initial'}),
            widgets.Text(description='شماره همراه:', style={'description_width': 'initial'}),
            widgets.Text(description='نام پدر:', style={'description_width': 'initial'}),
            widgets.Text(description='نام شهر یا استان:', style={'description_width': 'initial'}),
            widgets.Text(description='کد ملی:', style={'description_width': 'initial'}),
            widgets.Text(description='شماره کارت:', style={'description_width': 'initial'})
        ]
    else:  # صادرات
        fields = [
            widgets.Text(description='نام و نام خانوادگی:', style={'description_width': 'initial'}),
            widgets.Text(description='شماره همراه:', style={'description_width': 'initial'})
        ]

    # ایجاد دکمه جستجو
    search_button = widgets.Button(description="شروع جستجو", button_style='success')

    # ذخیره فیلدها و دکمه در ویجت
    search_form = widgets.VBox([
        widgets.HTML(f"<h3 style='color: #1E88E5; text-align: right;'>فیلترهای جستجوی بانک {bank_name} 🔍</h3>"),
        *fields,
        search_button
    ])

    # نمایش فرم
    display(search_form)

    # اتصال رویداد به دکمه جستجو
    search_button.on_click(on_search_clicked)

# تابع مدیریت جستجو
def on_search_clicked(b):
    global current_db, current_bank, search_results
    clear_output(wait=True)
    display(welcome_html)
    display(bank_dropdown)
    display(search_form)

    # جمع‌آوری پارامترهای جستجو
    search_params = []
    conditions = []
    other_fields_filled = False  # آیا حداقل یک فیلد غیر از کد ملی و تاریخ تولد پر شده است؟

    if current_bank == "ملی":
        fields = search_form.children[1:6]
        name, birth_date, mobile, national_code, card_no = [field.value for field in fields]

        # بررسی پر شدن سایر فیلدها (غیر از تاریخ تولد)
        other_fields_filled = any([name, mobile, national_code, card_no])
        
        if name:
            conditions.append(f"FULL_NAME LIKE '%{name}%'")
            search_params.append(f"نام: {name}")
        
        if birth_date:
            # اگر دقیقاً 4 رقم وارد شده و حداقل یک فیلد دیگر پر شده باشد
            if len(birth_date) == 4 and birth_date.isdigit() and other_fields_filled:
                conditions.append(f"BIRTH_DATE LIKE '{birth_date}%'")
                search_params.append(f"سال تولد: {birth_date}")
            else:
                conditions.append(f"BIRTH_DATE LIKE '%{birth_date}%'")
                search_params.append(f"تاریخ تولد: {birth_date}")
        
        if mobile:
            conditions.append(f"MOBILE LIKE '%{mobile}%'")
            search_params.append(f"موبایل: {mobile}")
        
        if national_code:
            # اگر دقیقاً 3 رقم وارد شده و حداقل یک فیلد دیگر پر شده باشد
            if len(national_code) == 3 and national_code.isdigit() and other_fields_filled:
                conditions.append(f"NATIONAL_CODE LIKE '{national_code}%'")
                search_params.append(f"سه رقم اول کدملی: {national_code}")
            else:
                conditions.append(f"NATIONAL_CODE LIKE '%{national_code}%'")
                search_params.append(f"کدملی: {national_code}")
        
        if card_no:
            conditions.append(f"CARD_NO LIKE '%{card_no}%'")
            search_params.append(f"کارت: {card_no}")

        table = "Melli"

    elif current_bank == "ملت":
        fields = search_form.children[1:8]
        name, birth_date, mobile, father_name, city, national_code, card_no = [field.value for field in fields]

        # بررسی پر شدن سایر فیلدها (غیر از تاریخ تولد)
        other_fields_filled = any([name, mobile, father_name, city, national_code, card_no])
        
        if name:
            conditions.append(f"FULL_NAME LIKE '%{name}%'")
            search_params.append(f"نام: {name}")
        
        if birth_date:
            # اگر دقیقاً 4 رقم وارد شده و حداقل یک فیلد دیگر پر شده باشد
            if len(birth_date) == 4 and birth_date.isdigit() and other_fields_filled:
                conditions.append(f"BIRTH_DATE LIKE '{birth_date}%'")
                search_params.append(f"سال تولد: {birth_date}")
            else:
                conditions.append(f"BIRTH_DATE LIKE '%{birth_date}%'")
                search_params.append(f"تاریخ تولد: {birth_date}")
        
        if mobile:
            conditions.append(f"MOBILE LIKE '%{mobile}%'")
            search_params.append(f"موبایل: {mobile}")
        
        if father_name:
            conditions.append(f"FATHER_NAME LIKE '%{father_name}%'")
            search_params.append(f"نام پدر: {father_name}")
        
        if city:
            conditions.append(f"(CITY_NAME LIKE '%{city}%' OR PROVINCE_NAME LIKE '%{city}%' OR BIRTH_CITY LIKE '%{city}%' OR BIRTH_PROVINCE LIKE '%{city}%' OR ADDRESS LIKE '%{city}%')")
            search_params.append(f"شهر/استان: {city}")
        
        if national_code:
            # اگر دقیقاً 3 رقم وارد شده و حداقل یک فیلد دیگر پر شده باشد
            if len(national_code) == 3 and national_code.isdigit() and other_fields_filled:
                conditions.append(f"NATIONAL_CODE LIKE '{national_code}%'")
                search_params.append(f"سه رقم اول کدملی: {national_code}")
            else:
                conditions.append(f"NATIONAL_CODE LIKE '%{national_code}%'")
                search_params.append(f"کدملی: {national_code}")
        
        if card_no:
            conditions.append(f"CARD_NO LIKE '%{card_no}%'")
            search_params.append(f"کارت: {card_no}")

        table = "Mellat"

    else:  # صادرات
        fields = search_form.children[1:3]
        name, mobile = [field.value for field in fields]

        if name:
            conditions.append(f"FullName LIKE '%{name}%'")
            search_params.append(f"نام: {name}")
        if mobile:
            conditions.append(f"user_phone_number LIKE '%{mobile}%'")
            search_params.append(f"موبایل: {mobile}")

        table = "Saderat"

    # بررسی حداقل یک فیلد پر شده باشد
    if not any(field.value for field in fields):
        print("⚠️ لطفاً حداقل یکی از فیلدها را پر کنید!")
        return

    # ساخت کوئری
    query = f"SELECT * FROM {table}"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # اجرای کوئری
    print(f"🔍 در حال جستجو در بانک {current_bank}...")
    start_time = time.time()
    result = current_db.execute(query).fetchdf()
    elapsed_time = time.time() - start_time

    if result.empty:
        print(f"❌ هیچ نتیجه‌ای یافت نشد! زمان جستجو: {elapsed_time:.2f} ثانیه")
        return

    # پاک‌سازی داده‌های تکراری
    print(f"✅ {len(result)} نتیجه اولیه یافت شد! زمان جستجو: {elapsed_time:.2f} ثانیه")
    print("🧹 در حال پاک‌سازی داده‌های تکراری...")
    
    cleaned_result = clean_duplicate_data(result, current_bank)
    
    print(f"✨ پس از حذف تکراری‌ها، {len(cleaned_result)} نتیجه معتبر باقی ماند.")

    # ذخیره نتایج
    search_results = (cleaned_result, search_params)

    # نمایش نتایج
    display(cleaned_result.head())

    # ایجاد دکمه دانلود PDF
    pdf_button = widgets.Button(description="دانلود PDF نتایج ⬇️", button_style='info')
    display(pdf_button)
    pdf_button.on_click(on_pdf_button_clicked)

# تابع ایجاد PDF
def on_pdf_button_clicked(b):
    global search_results, current_bank
    if not search_results:
        return

    data, params = search_results
    print(f"📊 در حال ایجاد گزارش PDF برای {len(data)} نتیجه...")

    # ایجاد PDF بر اساس بانک
    if current_bank == "ملی":
        pdf_data = create_melli_pdf(data, params)
        filename = "نتایج_بانک_ملی.pdf"
    elif current_bank == "ملت":
        pdf_data = create_mellat_pdf(data, params)
        filename = "نتایج_بانک_ملت.pdf"
    else:
        pdf_data = create_saderat_pdf(data, params)
        filename = "نتایج_بانک_صادرات.pdf"

    # ایجاد لینک دانلود
    download_link = create_download_link(pdf_data, filename)
    display(HTML(download_link))
    print(f"✅ گزارش PDF آماده دانلود است!")

# رابط کاربری
welcome_html = widgets.HTML(
    """<div style="text-align: center; color: #1565C0; padding: 20px; border: 2px solid #1E88E5; border-radius: 10px; background-color: #E3F2FD;">
    <h2 style="margin: 0; font-size: 22px;">🖥 به سامانه جامع اطلاعات مشتریان بانکی ایران خوش آمدید! 🇮🇷</h2>
    <p style="font-size: 16px;">🔍 برای جستجوی اطلاعات فرد مورد نظر، یکی از بانک‌ها را انتخاب و حداقل یکی از فیلدها را تکمیل کنید!</p>
    </div>"""
)

bank_dropdown = widgets.Dropdown(
    options=["تعیین نشده!", "ملی", "ملت", "صادرات"],
    value="تعیین نشده!",
    description='بانک:',
    style={'description_width': 'initial'},
    layout={'width': '300px'}
)

# دانلود فونت‌های ایران‌سانس
if not os.path.exists('IRANSansWeb_Medium.ttf'):
    !wget "https://github.com/akiarostami/iransans/raw/main/files/IRANSansWeb_Medium.ttf" -O IRANSansWeb_Medium.ttf -q

if not os.path.exists('IRANSansWeb_Bold.ttf'):
    !wget "https://github.com/akiarostami/iransans/raw/main/files/IRANSansWeb_Bold.ttf" -O IRANSansWeb_Bold.ttf -q

# دانلود لوگوها
logo_ids = {
    "melli_logo.png": "139TUGX1KriBBnJHznFP__rPB02_BRdJm",
    "mellat_logo.png": "17-4bKtYs4fC-b4Ilngq3GBMWrATiJIOs",
    "saderat_logo.png": "174UhniE7YGbAsRq7p6oX_eZtT_VttDzR"
}

for filename, file_id in logo_ids.items():
    if not os.path.exists(filename):
        download_file(file_id, filename)

# نمایش اولیه
clear_output(wait=True)
display(welcome_html)
display(bank_dropdown)

# تنظیم رویداد تغییر بانک
bank_dropdown.observe(on_bank_change, names='value')