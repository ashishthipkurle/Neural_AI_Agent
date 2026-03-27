from PIL import Image, ImageDraw, ImageFont
import os

# Create directory if it doesn't exist
images_dir = r"D:\All Projects\Projects mad by Albert\react_business_site\public\images"
os.makedirs(images_dir, exist_ok=True)

# List of new books that need images
books = [
    "The Hobbit",
    "Harry Potter and the Sorcerer's Stone", 
    "The Catcher in the Rye",
    "Lord of the Flies",
    "Animal Farm"
]

# Create a simple placeholder image for each book
def create_placeholder(title, filename):
    # Create a blank image
    img = Image.new('RGB', (300, 400), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    
    # Try to add text
    try:
        # Try to use a better font if available
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Calculate text position
    bbox = d.textbbox((0, 0), title, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (300 - text_width) / 2
    y = (400 - text_height) / 2
    
    # Draw text
    d.text((x, y), title, fill=(255, 255, 0), font=font)
    
    # Save image
    img.save(os.path.join(images_dir, filename))

# Create images for new books
for book in books:
    filename = book.lower().replace(" ", "-").replace("'", "") + ".jpg"
    create_placeholder(book, filename)
    print(f"Created {filename}")

print("All placeholder images created successfully!")