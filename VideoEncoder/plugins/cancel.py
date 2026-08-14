from pyrogram import Client, filters
from ..utils.helper import check_chat
from ..svcs.task_manager import task_manager
from ..db.status import status_db
from ..core.cfg import cfg

async def is_admin(user_id):
    if user_id in cfg.OWNER_ID or user_id in cfg.SUDO_USERS:
        return True
    
    get_sudo = (await status_db.get_sudo_users()).split()
    return str(user_id) in get_sudo

@Client.on_message(filters.command(['cancel', 'c', 'cancel_1', 'c_1']))
async def cancel_handler(app, message):
    if not await check_chat(message, chat='Both'):
        return
    
    user_id = message.from_user.id if message.from_user else None
    is_user_admin = await is_admin(user_id)
    
    args = message.text.split(None, 1)
    
    if len(args) < 2:
        tasks = task_manager.get_all_tasks()
        if not tasks:
            await message.reply("▸ <b>Tasks</b>\nStatus: ● No Active Tasks\n\nNo downloads or encodes running.")
            return
        
        text = "▸ <b>Active Tasks</b>\n\n"
        user_tasks = 0
        
        for tid, task in tasks.items():
            task_type = task.get("type", "unknown")
            task_owner = task.get("user_id")
            emoji = "⬇️" if task_type == "download" else "🔄"
            
            if is_user_admin or task_owner == user_id:
                owner_label = ""
                if is_user_admin and task_owner:
                    owner_label = f" (User: {task_owner})"
                text += f"{emoji} <code>{tid}</code> - {task_type.capitalize()}{owner_label}\n"
                user_tasks += 1
        
        if user_tasks == 0:
            await message.reply("▸ <b>Tasks</b>\nStatus: ● No Active Tasks\n\nYou have no running tasks.")
            return
        
        text += "\n<b>Usage:</b> <code>/cancel [id]</code>"
        await message.reply(text)
        return
    
    task_id = args[1].strip().lower()
    
    task = task_manager.get_task(task_id)
    if not task:
        await message.reply(f"▸ <b>Cancel</b>\nStatus: ✗ Failed\nTask `{task_id}` not found.")
        return
    
    task_owner = task.get("user_id")
    
    if not is_user_admin and task_owner != user_id:
        await message.reply(
            "▸ <b>Cancel</b>\n"
            "Status: ✗ Access Denied\n\n"
            "You can only cancel your own tasks."
        )
        return
    
    success, result = await task_manager.cancel_task(task_id)
    
    if success:
        await message.reply(f"▸ <b>Cancelled</b>\nStatus: ● Success\n{result}")
    else:
        await message.reply(f"▸ <b>Cancel</b>\nStatus: ✗ Failed\n{result}")
