from app.todos import bp
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import TodoList, TodoItem, FamilyMembers, User
from app.todos.forms import TodoListForm, TodoItemForm
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _my_lists():
    """Return all lists the current user owns or can see (family-shared)."""
    family = current_user.get_active_family()
    conditions = [TodoList.user_id == current_user.id]
    if family:
        conditions.append(
            and_(TodoList.family_id == family.id, TodoList.family_id.isnot(None))
        )
    return TodoList.query.filter(or_(*conditions)).order_by(
        TodoList.created_at.asc()
    ).all()


def _family_members():
    """Return (id, username) pairs for the active family."""
    family = current_user.get_active_family()
    if not family:
        return [(0, 'Unassigned')]
    rows = db.session.query(User.id, User.username).join(
        FamilyMembers, FamilyMembers.user_id == User.id
    ).filter(FamilyMembers.family_id == family.id).all()
    return [(0, 'Unassigned')] + [(r.id, r.username) for r in rows]


def _can_access_list(todo_list):
    """Check the current user can view/edit this list."""
    if todo_list.user_id == current_user.id:
        return True
    family = current_user.get_active_family()
    if family and todo_list.family_id == family.id:
        return True
    return False


# ---------------------------------------------------------------------------
# Hub - shows all lists & quick-add
# ---------------------------------------------------------------------------

@bp.route('/todos')
@login_required
def todo_hub():
    lists = _my_lists()

    # Ensure at least one default list exists
    if not lists:
        default = TodoList(user_id=current_user.id, title='My Tasks',
                           icon='fa-list-check', color='#3A8F85')
        db.session.add(default)
        db.session.commit()
        lists = [default]

    list_form = TodoListForm()
    item_form = TodoItemForm()
    item_form.assigned_to.choices = _family_members()

    # Stats
    all_items = []
    for lst in lists:
        all_items.extend(lst.items.all())

    today = date.today()
    total = len(all_items)
    done = sum(1 for i in all_items if i.completed)
    overdue = sum(1 for i in all_items if not i.completed and i.due_date and i.due_date < today)
    due_today = sum(1 for i in all_items if not i.completed and i.due_date == today)
    upcoming_7 = sum(1 for i in all_items if not i.completed and i.due_date
                     and today < i.due_date <= today + timedelta(days=7))

    # Active list (selected via ?list= param, default to first)
    active_list_id = request.args.get('list', type=int)
    active_list = None
    if active_list_id:
        active_list = TodoList.query.get(active_list_id)
        if active_list and not _can_access_list(active_list):
            active_list = None
    if not active_list:
        active_list = lists[0]

    # Filter
    filt = request.args.get('filter', 'active')  # active, all, completed, overdue, today
    items_q = TodoItem.query.filter_by(list_id=active_list.id)
    if filt == 'active':
        items_q = items_q.filter_by(completed=False)
    elif filt == 'completed':
        items_q = items_q.filter_by(completed=True)
    elif filt == 'overdue':
        items_q = items_q.filter(TodoItem.completed == False,
                                  TodoItem.due_date < today)
    elif filt == 'today':
        items_q = items_q.filter(TodoItem.completed == False,
                                  TodoItem.due_date == today)

    items = items_q.order_by(
        TodoItem.completed.asc(),
        TodoItem.sort_order.asc(),
        TodoItem.due_date.asc().nullslast(),
        TodoItem.created_at.asc()
    ).all()

    tomorrow = today + timedelta(days=1)

    return render_template('todos/todo_hub.html',
                           lists=lists,
                           active_list=active_list,
                           items=items,
                           list_form=list_form,
                           item_form=item_form,
                           today=today,
                           tomorrow=tomorrow,
                           filt=filt,
                           stats={'total': total, 'done': done, 'overdue': overdue,
                                  'due_today': due_today, 'upcoming_7': upcoming_7})


# ---------------------------------------------------------------------------
# List CRUD
# ---------------------------------------------------------------------------

@bp.route('/todos/list/new', methods=['POST'])
@login_required
def create_list():
    form = TodoListForm()
    if form.validate_on_submit():
        family = current_user.get_active_family()
        lst = TodoList(
            user_id=current_user.id,
            title=form.title.data.strip(),
            color=form.color.data,
            icon=form.icon.data,
            family_id=family.id if form.shared.data == 'family' and family else None,
        )
        db.session.add(lst)
        db.session.commit()
        flash(f'List "{lst.title}" created.', 'success')
        return redirect(url_for('todos.todo_hub', list=lst.id))
    flash('Could not create list.', 'danger')
    return redirect(url_for('todos.todo_hub'))


@bp.route('/todos/list/<int:id>/edit', methods=['POST'])
@login_required
def edit_list(id):
    lst = TodoList.query.get_or_404(id)
    if not _can_access_list(lst):
        flash('Access denied.', 'danger')
        return redirect(url_for('todos.todo_hub'))

    lst.title = request.form.get('title', lst.title).strip()[:128]
    lst.color = request.form.get('color', lst.color)
    lst.icon = request.form.get('icon', lst.icon)
    shared = request.form.get('shared', 'personal')
    family = current_user.get_active_family()
    lst.family_id = family.id if shared == 'family' and family else None
    db.session.commit()
    flash(f'List "{lst.title}" updated.', 'success')
    return redirect(url_for('todos.todo_hub', list=lst.id))


@bp.route('/todos/list/<int:id>/delete', methods=['POST'])
@login_required
def delete_list(id):
    lst = TodoList.query.get_or_404(id)
    if lst.user_id != current_user.id:
        flash('Only the list owner can delete it.', 'danger')
        return redirect(url_for('todos.todo_hub'))
    title = lst.title
    db.session.delete(lst)
    db.session.commit()
    flash(f'List "{title}" deleted.', 'info')
    return redirect(url_for('todos.todo_hub'))


# ---------------------------------------------------------------------------
# Item CRUD
# ---------------------------------------------------------------------------

@bp.route('/todos/item/new', methods=['POST'])
@login_required
def create_item():
    form = TodoItemForm()
    form.assigned_to.choices = _family_members()
    list_id = request.form.get('list_id', type=int)
    lst = TodoList.query.get_or_404(list_id)
    if not _can_access_list(lst):
        flash('Access denied.', 'danger')
        return redirect(url_for('todos.todo_hub'))

    if form.validate_on_submit():
        item = TodoItem(
            list_id=lst.id,
            user_id=current_user.id,
            title=form.title.data.strip(),
            notes=form.notes.data.strip() if form.notes.data else None,
            priority=form.priority.data,
            due_date=form.due_date.data,
            due_time=form.due_time.data,
            assigned_to=form.assigned_to.data if form.assigned_to.data else None,
        )
        db.session.add(item)
        db.session.commit()
        flash('Task added.', 'success')
    else:
        flash('Could not add task.', 'danger')
    return redirect(url_for('todos.todo_hub', list=lst.id))


@bp.route('/todos/item/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_item(id):
    item = TodoItem.query.get_or_404(id)
    lst = TodoList.query.get_or_404(item.list_id)
    if not _can_access_list(lst):
        flash('Access denied.', 'danger')
        return redirect(url_for('todos.todo_hub'))

    item.completed = not item.completed
    if item.completed:
        item.completed_at = datetime.utcnow()
        item.completed_by = current_user.id
    else:
        item.completed_at = None
        item.completed_by = None
    db.session.commit()

    # AJAX support
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(ok=True, completed=item.completed)

    return redirect(url_for('todos.todo_hub', list=lst.id))


@bp.route('/todos/item/<int:id>/edit', methods=['POST'])
@login_required
def edit_item(id):
    item = TodoItem.query.get_or_404(id)
    lst = TodoList.query.get_or_404(item.list_id)
    if not _can_access_list(lst):
        flash('Access denied.', 'danger')
        return redirect(url_for('todos.todo_hub'))

    item.title = request.form.get('title', item.title).strip()[:256]
    item.notes = request.form.get('notes', item.notes or '')[:1000] or None
    item.priority = request.form.get('priority', item.priority)
    due_str = request.form.get('due_date', '')
    if due_str:
        try:
            item.due_date = datetime.strptime(due_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    else:
        item.due_date = None
    time_str = request.form.get('due_time', '')
    if time_str:
        try:
            item.due_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            pass
    else:
        item.due_time = None
    assigned = request.form.get('assigned_to', type=int)
    item.assigned_to = assigned if assigned else None
    db.session.commit()
    flash('Task updated.', 'success')
    return redirect(url_for('todos.todo_hub', list=lst.id))


@bp.route('/todos/item/<int:id>/delete', methods=['POST'])
@login_required
def delete_item(id):
    item = TodoItem.query.get_or_404(id)
    lst = TodoList.query.get_or_404(item.list_id)
    if not _can_access_list(lst):
        flash('Access denied.', 'danger')
        return redirect(url_for('todos.todo_hub'))

    list_id = item.list_id
    db.session.delete(item)
    db.session.commit()
    flash('Task deleted.', 'info')
    return redirect(url_for('todos.todo_hub', list=list_id))


# ---------------------------------------------------------------------------
# API endpoint for calendar integration (returns JSON)
# ---------------------------------------------------------------------------

@bp.route('/todos/api/calendar')
@login_required
def api_calendar_items():
    """Return to-do items with due dates for calendar rendering."""
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else date.today().replace(day=1)
        end = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else (start + timedelta(days=42))
    except ValueError:
        start = date.today().replace(day=1)
        end = start + timedelta(days=42)

    lists = _my_lists()
    list_ids = [l.id for l in lists]
    list_map = {l.id: l for l in lists}

    items = TodoItem.query.filter(
        TodoItem.list_id.in_(list_ids),
        TodoItem.due_date >= start,
        TodoItem.due_date <= end,
    ).order_by(TodoItem.due_date.asc()).all()

    result = []
    for item in items:
        lst = list_map.get(item.list_id)
        result.append({
            'id': item.id,
            'title': item.title,
            'due_date': item.due_date.isoformat(),
            'due_time': item.due_time.strftime('%H:%M') if item.due_time else None,
            'priority': item.priority,
            'completed': item.completed,
            'list_title': lst.title if lst else '',
            'list_color': lst.color if lst else '#666',
            'list_icon': lst.icon if lst else 'fa-list-check',
        })
    return jsonify(result)
