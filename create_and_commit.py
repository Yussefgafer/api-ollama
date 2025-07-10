# create_and_commit.py
import os
import sys
import subprocess

def create_and_commit_file(filename, content, commit_message, branch_name):
    """
    ينشئ أو يعدل ملفًا ويرفعه إلى مستودع Git.

    Args:
        filename (str): اسم الملف المراد إنشاؤه أو تعديله.
        content (str): محتوى الملف.
        commit_message (str): رسالة الالتزام (commit message).
        branch_name (str): اسم الفرع (branch) الذي سيتم الرفع إليه.
    """
    try:
        # 1. كتابة المحتوى إلى الملف
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"تم إنشاء/تعديل الملف: {filename}")

        # 2. إعداد Git (مهم لعمل GitHub Actions)
        subprocess.run(['git', 'config', 'user.name', '"GitHub Actions Bot"'], check=True)
        subprocess.run(['git', 'config', 'user.email', '"github-actions[bot]@users.noreply.github.com"'], check=True)
        
        # 3. إضافة الملف إلى Git
        subprocess.run(['git', 'add', filename], check=True)
        print(f"تم إضافة الملف {filename} إلى منطقة التجهيز.")

        # 4. الالتزام بالتغييرات (Commit)
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        print(f"تم الالتزام بالتغييرات: '{commit_message}'")

        # 5. رفع التغييرات (Push)
        # TOKEN: هو Personal Access Token (PAT) الذي تم تكوينه في GitHub Secrets
        # GITHUB_REPOSITORY: متغير بيئة يوفر اسم المستودع (owner/repo)
        repo_url = f"https://x-access-token:{os.environ['TOKEN']}@github.com/{os.environ['GITHUB_REPOSITORY']}.git"
        subprocess.run(['git', 'push', repo_url, branch_name], check=True)
        print(f"تم رفع التغييرات بنجاح إلى الفرع {branch_name}.")

    except subprocess.CalledProcessError as e:
        print(f"خطأ في أمر Git: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"حدث خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # يتم تمرير الوسائط من GitHub Action
    if len(sys.argv) < 5:
        print("الاستخدام: python create_and_commit.py <filename> <content> <commit_message> <branch_name>")
        sys.exit(1)

    filename = sys.argv[1]
    content = sys.argv[2]
    commit_message = sys.argv[3]
    branch_name = sys.argv[4]

    create_and_commit_file(filename, content, commit_message, branch_name)