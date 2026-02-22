from PIL import Image, ImageDraw, ImageFont
import os

# Create icons directory
os.makedirs('static/icons', exist_ok=True)

# Create a simple tea cup icon
def create_icon(size):
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw tea cup shape (simple)
    cup_color = (245, 158, 11)  # Amber color
    text_color = (255, 255, 255, 255)  # White
    
    # Draw cup
    cup_width = size * 0.6
    cup_height = size * 0.4
    cup_x = (size - cup_width) // 2
    cup_y = (size - cup_height) // 2
    
    # Cup body
    draw.rectangle([cup_x, cup_y, cup_x + cup_width, cup_y + cup_height], 
                fill=cup_color, outline=None)
    
    # Cup handle
    handle_width = cup_width * 0.2
    handle_x = cup_x + cup_width
    draw.ellipse([handle_x, cup_y, handle_x + handle_width, cup_y + cup_height * 0.6], 
               fill=cup_color, outline=None)
    
    # Steam lines
    for i in range(3):
        steam_x = cup_x + cup_width // 4 + i * (cup_width // 8)
        steam_y = cup_y - size * 0.1 - i * size * 0.05
        draw.line([steam_x, steam_y, steam_x, steam_y - size * 0.1], 
                 fill=text_color, width=size//50)
    
    # Add text "VT" for Vijeta Tea
    try:
        font_size = size // 6
        font = ImageFont.load_default()
        text = "VT"
        bbox = draw.textbbox(text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (size - text_width) // 2
        text_y = cup_y + cup_height + size * 0.1
        draw.text((text_x, text_y), text, fill=text_color, font=font)
    except:
        pass
    
    return img

# Generate different icon sizes
sizes = [72, 96, 128, 144, 152, 192, 384, 512]

for size in sizes:
    icon = create_icon(size)
    icon.save(f'static/icons/icon-{size}x{size}.png')
    print(f"Created icon {size}x{size}")

print("All icons generated successfully!")
