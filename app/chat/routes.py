from app.chat import bp
from flask import render_template, request, redirect, url_for, flash, jsonify
from app.models import Message, User, Family
from app.chat.forms import MessageForm
from flask_login import login_required, current_user
from app import db, socketio
from datetime import datetime, timedelta
from app.decorators import active_family_required

## Messaging Routes
@bp.route('/familychat', methods=['GET', 'POST'])
@login_required
@active_family_required
def familychat():
    form = MessageForm()

    if form.validate_on_submit() and form.content.data.strip():
        message = Message(user_id=current_user.id, content=form.content.data.strip())
        db.session.add(message)
        db.session.commit()

        socketio.emit('message_received', {
            'id': message.id,
            'user_id': message.user_id,
            'username': current_user.username,
            'content': message.content,
            'timestamp': message.timestamp.strftime("%d-%m-%Y %H:%M:%S")
        })

        return jsonify({'status': 'success'})

    # Load full message history **only on page load** (not during message sending)
    #messages = Message.query.order_by(Message.timestamp.asc()).all()

    user_families = current_user.families  # Assuming this is correctly set up
    messages = Message.query.filter(Message.user.has(User.families.any(Family.id.in_([fam.id for fam in user_families])))).order_by(Message.timestamp.asc()).all()



    return render_template('chat/familychat.html', 
                            title='Family Chat',
                            form=form,
                            messages=messages)

@bp.route('/load_messages')
@login_required
@active_family_required
def load_messages():
    last_message_id = request.args.get("last_message_id", type=int)
    if not last_message_id:
        return jsonify({'error': 'Invalid message ID'}), 400

    user_families = current_user.families
    messages = Message.query.filter(
        Message.id < last_message_id,
        Message.user.has(User.families.any(Family.id.in_([fam.id for fam in user_families]))),
    ).order_by(Message.timestamp.asc()).limit(10).all()

    return jsonify([{ 
        'id': msg.id, 
        'deleted': msg.deleted,
        'username': msg.user.username, 
        'content': msg.content if not msg.deleted else None, 
        'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    } for msg in messages])


@bp.route('/delete_message/<int:message_id>', methods=['POST'])
@login_required
@active_family_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)

    # Ensure only the message owner or admin can delete
    if message.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403

    message.deleted = True
    db.session.commit()

    # Emit WebSocket event ONLY after successful deletion
    socketio.emit('message_deleted', {
        'message_id': message.id,
        'username': message.user.username,
        'timestamp': message.timestamp.strftime("%d-%m-%Y %H:%M:%S")
    })

    return jsonify({'status': 'success'})