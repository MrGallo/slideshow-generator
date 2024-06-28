import csv
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont

# Visual settings
WIDTH = 1920
HEIGHT = 1080
BG_COLOR = "#212121"
PRIMARY_COLOR = "#ffffff"    # for student name
SECONDARY_COLOR = "#adadad"  # for achievements
PRIMARY_FONT_PATH = "fonts/Cambo-Regular.ttf"
SECONDARY_FONT_PATH = "fonts/ArialTh.ttf"

# Data
TSV_FILE_PATH = "data/Potential Grads 2023-24 - Slideshow Ready.tsv"
TABLE_FIELDS = "status student_id last_name first_name ont_scholar honour_roll shsm awards".split()

# Image paths
PHOTOS_BASE_DIR = pathlib.Path("images")
SCHOOL_LOGO_PATH = PHOTOS_BASE_DIR / "school_logo.png"

# The subdirectories in your photos base dir
# The topmost directories have the higher priority
PHOTO_DIRECTORIES = [
    "RETAKES",
    "GRAD_PHOTOS",
    "EXTRAS",
]

OUTPUT_PDF_FILENAME = "slideshow.pdf"


LEFT_MIDPOINT = int(WIDTH * 0.29)
RIGHT_MIDPOINT = int(WIDTH * (1-0.23))

def main():
    # READ TSV
    
    with open(TSV_FILE_PATH, "r") as f:
        read_tsv = csv.reader(f, delimiter="\t")
        data = list(read_tsv)[1:]
    
    students = []
    student_ids = set()
    student_ids_not_attending = set()
    for row in data:
        if row[1] == "":
            print(f"ISSUE: Student ({row[2]}) has no student number.")
            continue
        
        if 'x' in row[0].lower():
            student_ids_not_attending.add(row[1])
            continue

        student = {}
        for key, value in zip(TABLE_FIELDS, row):
            student[key] = value
        
        # check for duplicate Student IDs
        id = student["student_id"]
        if id in student_ids:
            print(f"ERROR: Student ID duplicate ({id}).")
        student_ids.add(id)
        
        student["awards"] = [a.strip() for a in student["awards"].split(";") if a != ""]
        if student["ont_scholar"]:
            student["awards"] = ["Ontario Scholar"] + student["awards"]
        if student["honour_roll"]:
            student["awards"] = ["Honour Roll"] + student["awards"]
        if (shsm := student["shsm"].upper()) != "":
            shsm_text = {
                "HLW": "Health and Wellness SHSM", 
                "AVA": "Aerospace and Aviation SHSM",
                "CSE": "Justice, Community Safety & Emergency Services SHSM"}[shsm]
            student["awards"] = [shsm_text] + student["awards"]

        students.append(student)
    
    # MATCH STUDENTS WITH PHOTOS
    students_by_id = dict((s["student_id"], s) for s in students)

    for subdir in PHOTO_DIRECTORIES:
        # Scan all available photos
        for file in pathlib.Path(PHOTOS_BASE_DIR / subdir).iterdir():
            if file.suffix.lower() == ".jpg":
                student_id = file.stem
                image_key_name = "image_file"
                try:
                    # Try to find a student record from the spreadsheet with that student id
                    # If we haven't already found an image for them, add it
                    if image_key_name not in students_by_id[student_id].keys():
                        students_by_id[student_id][image_key_name] = file
                except KeyError:
                    # The case where we have a photo with a particular student id
                    # But they are not in the slideshow
                    if student_id not in student_ids_not_attending:
                        print(f"ISSUE: The image '{file.as_posix()}' cannot be found in the student list.")

    for s in students:
        if "image_file" not in s.keys():
            print(f"ISSUE: Missing photo for {s['first_name']} {s['last_name']} ({s['student_id']}).")


    # CREATE SLIDES
    base_template = draw_base()

    ## CREATE NEW SLIDE
    slides = []
    # for s in (s for s in students if len(s["awards"]) > 0):  # awards only
    for n, s in enumerate(students, 1):
        new_slide = base_template.copy()
        name = f"{s['first_name']} {s['last_name']}"
        add_name(name, new_slide, has_awards=len(s["awards"]) > 0)

        if len(s["awards"]) > 3:
            print(f"ISSUE: More than 3 awards. Slide #{n}, name: {name}")
            s["awards"] = [", ".join(s["awards"])]
        add_achievements(s["awards"], new_slide)
        if "image_file" in s.keys():
            add_image(s["image_file"], new_slide)

        # new_slide.save('pil_img.png')
        slides.append(new_slide)

    slides[0].save(OUTPUT_PDF_FILENAME, save_all=True, append_images=slides[1:])


def draw_base():
    bg = Image.new("RGB", (WIDTH, HEIGHT), color=BG_COLOR)
    logo = Image.open(SCHOOL_LOGO_PATH)
    logo_side = logo

    # SMALL LOGO
    small_logo = logo.resize((int(logo.width * 0.30), int(logo.height * 0.30)))
    left = LEFT_MIDPOINT - small_logo.width // 2
    top = 175
    right = left + small_logo.width
    bottom = top + small_logo.height
    bg.paste(small_logo, (left, top, right, bottom), mask=small_logo)

    # LOGO
    left = RIGHT_MIDPOINT - logo_side.width//2
    top = HEIGHT // 2 - logo_side.height // 2
    right = left + logo_side.width
    bottom = top + logo_side.height
    bg.paste(logo_side, (left, top, right, bottom), mask=logo_side)
    return bg


def add_image(image_file, slide: Image):
    image = Image.open(image_file)  # 0.2 ms

    # check for cache folder
    cache_path = pathlib.Path("images/cache")
    try:
        pathlib.Path.mkdir(cache_path)
    except FileExistsError:
        # already exists, move on
        pass
    
    # look for cached version of student photo, if not found create
    try:
        image = Image.open(cache_path / image_file.name)  
    except FileNotFoundError:
        # resize and save to cache
        h = int(HEIGHT * 0.9)
        ratio = h / image.height
        w = int(image.width * ratio)
        image = image.resize((w, h))  # 75 ms
        image.save(cache_path / image_file.name)

    # Place image
    left = RIGHT_MIDPOINT - image.width//2
    top = HEIGHT // 2 - image.height // 2
    right = left + image.width
    bottom = top + image.height
    slide.paste(image, (left, top, right, bottom))


def add_name(name_text, image, has_awards=False):
    draw = ImageDraw.Draw(image)
    name_text_height = int(HEIGHT * 0.13)

    while True:
        name_font = ImageFont.truetype(PRIMARY_FONT_PATH, name_text_height)
        # w, h = draw.textsize(name_text, name_font)
        top, left, w, h = draw.textbbox((0, 0), name_text, name_font)
        if w < WIDTH * 0.5:
            break
        name_text_height -= 1
            
    x = LEFT_MIDPOINT - (w//2)
    y = int(HEIGHT * 0.45 - (h//2))
    if has_awards:
        y = int(HEIGHT * 0.40 - (h//2))
    draw.text((x, y), name_text, font=name_font, fill=PRIMARY_COLOR)


def add_achievements(awards, image):
    if len(awards) == 0:
        return
    draw = ImageDraw.Draw(image)
    award_text_height = int(HEIGHT * 0.10)
    awards = ["\n".join(textwrap.wrap(text, width=30)) for text in awards]
    award_text = "\n".join(awards)

    while True:
        award_font= ImageFont.truetype(SECONDARY_FONT_PATH, award_text_height)
        # w, h = draw.textsize(award_text, award_font)
        top, left, w, h = draw.textbbox((0, 0), award_text, award_font)
        if w < WIDTH * 0.45 and h < HEIGHT * 0.33:
            break
        award_text_height -= 1
        
    x = LEFT_MIDPOINT - (w//2)
    y = int(HEIGHT * 2 / 3) - (h//2)
    draw.text((x, y), award_text, font=award_font, fill=SECONDARY_COLOR, spacing=HEIGHT * 0.03, align="center")


if __name__ == "__main__":
    main()