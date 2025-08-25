import pandas as pd
df=pd.read_excel("research.xlsx", header=1)
teacher_id={}
counter=1

for name in df['First Author Name'].dropna().unique():
    teacher_id[name.strip().lower()]=f"T{counter:03d}"
    counter+=1

df["Teacher ID"]=df['First Author Name'].str.strip().str.lower().map(teacher_id)
df.to_excel("research_with_ids.xlsx", index=False)
print("Unique IDs generated and saved to research_with_ids.xlsx")