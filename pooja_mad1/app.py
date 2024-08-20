from flask import Flask, render_template, redirect, url_for, request, session,flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///influencer_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

app.secret_key = 'your_secret_key'
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # Store hashed passwords
    role = db.Column(db.String(50), nullable=False)  # Admin, Sponsor, Influencer
    flagged = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    budget = db.Column(db.Float, nullable=False)
    ind_pay = db.Column(db.Float, nullable=False)
    visibility = db.Column(db.String(50), nullable=False)  # public, private
    goals = db.Column(db.Text, nullable=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    ad_requests = db.relationship('AdRequest', backref='campaign', lazy=True)
    flagged = db.Column(db.Boolean, default=False)

class AdRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    messages = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=False)
    payment_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending')  # Pending, Accepted, Rejected
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    influencer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    influencer = db.relationship('User', backref='ad_requests', lazy=True)
    requests_from_inf = db.relationship('req_from_inf', backref='ad_request', lazy=True)

class req_from_inf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    req_amount = db.Column(db.Float, nullable=False)
    ad_request_id = db.Column(db.Integer, db.ForeignKey('ad_request.id'), nullable=False)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/campaigns')
def campaigns():
    campaigns = Campaign.query.all()
    return render_template('campaign.html', campaigns=campaigns)

@app.route('/ad_requests')
def ad_requests():
    ad_requests = AdRequest.query.all()
    return render_template('ad_request.html', ad_requests=ad_requests)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        role = request.form['role']

        # Create a new User object and set the password
        new_user = User(name=name, role=role)
        new_user.set_password(password)

        # Add the user to the database
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        user = User.query.filter_by(name=name).first()

        if user and user.check_password(password):
            session['user_id'] = user.id  # Set the user ID in the session
            session['user_name'] = user.name
            if user.role == 'Influencer':
                return redirect(url_for('influencer_dashboard'))
            elif user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('sponsor_dashboard'))

        return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/sponsor_dashboard", methods=["GET", "POST"])
def sponsor_dashboard():
    if request.method == 'POST':
        # Handle campaign creation
        name = request.form['name']
        description = request.form['description']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        budget = float(request.form['budget'])
        ind_pay=float(request.form["ind_pay"])
        visibility = request.form['visibility']
        goals = request.form['goals']
        sponsor_id = session['user_id']  # Use the session to get the sponsor ID

        new_campaign = Campaign(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            ind_pay=ind_pay,
            visibility=visibility,
            goals=goals,
            sponsor_id=sponsor_id
        )

        db.session.add(new_campaign)
        db.session.commit()

        return redirect("/sponsor_dashboard")

    search_query = request.args.get('search_query', '')
    if search_query:
        search_results = User.query.filter(User.role == 'Influencer', User.name.ilike(f'%{search_query}%')).all()
    else:
        search_results = []

    influencers = User.query.filter_by(role='Influencer').all()
    campaigns = Campaign.query.filter_by(sponsor_id=session['user_id']).all()

    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user = User.query.get(session['user_id'])

    if user.role != 'Sponsor':
        return redirect(url_for('index'))  # Redirect to index if not an admin
    

    user_name = session.get('user_name')

    all_req = AdRequest.query.all()
    req=req_from_inf.query.all()
    return render_template("sponsor_dashboard.html", user=user_name,campaigns=campaigns, influencers=influencers, req_from_inf=req,all_req=all_req, search_results=search_results)

@app.route('/influencer_dashboard', methods=["GET", "POST"])
def influencer_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user_id = session['user_id']  # Retrieve the user ID from the session

    # Fetch ad requests where the influencer_id matches the logged-in user's ID
    ad_requests = AdRequest.query.filter_by(influencer_id=user_id).all()
    public_campaigns = Campaign.query.filter_by(visibility="public").all()

    # Logic to handle ad request creation for public campaigns
    if request.method == 'POST':
        campaign_id = request.form.get('campaign_id')
        requirements = request.form.get('requirements')
        payment_amount = request.form.get('payment_amount')

        new_ad_request = AdRequest(
            requirements=requirements,
            payment_amount=float(payment_amount),
            status='Pending',
            campaign_id=int(campaign_id),
            influencer_id=user_id
        )

        db.session.add(new_ad_request)
        db.session.commit()

        return redirect(url_for('influencer_dashboard'))
    
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user = User.query.get(session['user_id'])

    if user.role != 'Influencer':
        return redirect(url_for('index'))  # Redirect to index if not an admin
    
    
    user_name = session.get('user_name')

    return render_template('influencer_dashboard.html', user=user_name,ad_requests=ad_requests, public_campaigns=public_campaigns)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user = User.query.get(session['user_id'])

    if user.role != 'Admin':
        return redirect(url_for('index'))  # Redirect to index if not an admin
    
    user_name = session.get('user_name')

    # Fetch statistics
    total_users = User.query.count()
    total_campaigns = Campaign.query.count()
    public_campaigns = Campaign.query.filter_by(visibility='public').count()
    private_campaigns = Campaign.query.filter_by(visibility='private').count()
    total_ad_requests = AdRequest.query.count()
    pending_ad_requests = AdRequest.query.filter_by(status='Pending').count()
    accepted_ad_requests = AdRequest.query.filter_by(status='Accepted').count()
    rejected_ad_requests = AdRequest.query.filter_by(status='Rejected').count()

    # Fetch flagged campaigns/users (assuming a 'flagged' attribute exists)
    flagged_campaigns = Campaign.query.filter_by(flagged=True).all()
    flagged_users = User.query.filter_by(flagged=True).all()
    all_campaigns = Campaign.query.all()
    all_user=User.query.all()
    all_adreq=AdRequest.query.all()
    return render_template('admin_dashboard.html', 
                           total_users=total_users, 
                           total_campaigns=total_campaigns,
                           public_campaigns=public_campaigns, 
                           private_campaigns=private_campaigns,
                           total_ad_requests=total_ad_requests, 
                           pending_ad_requests=pending_ad_requests,
                           accepted_ad_requests=accepted_ad_requests, 
                           rejected_ad_requests=rejected_ad_requests,
                           flagged_campaigns=flagged_campaigns,
                           flagged_users=flagged_users,
                           user=user_name,all_campaigns=all_campaigns,all_user=all_user,all_adreq=all_adreq)


@app.route('/search_campaigns', methods=['GET'])
def search_campaigns():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user_id = session['user_id']  # Retrieve the user ID from the session

    # Fetch ad requests where the influencer_id matches the logged-in user's ID
    ad_requests = AdRequest.query.filter_by(influencer_id=user_id).all()
    public_campaigns = Campaign.query.filter_by(visibility="public").all()

    # Get search parameters from the form
    name = request.args.get('name')
    budget = request.args.get('budget', type=float)

    # Base query: search for public campaigns
    query = Campaign.query.filter_by(visibility='public')

    # Add filters based on search parameters
    if name:
        query = query.filter(Campaign.name.ilike(f'%{name}%'))
    if budget is not None:
        query = query.filter(Campaign.budget <= budget)

    # Execute the query and get results
    campaigns = query.all()

    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    user = User.query.get(session['user_id'])

    if user.role != 'Influencer':
        return redirect(url_for('index'))  # Redirect to index if not an admin
    
    
    user_name = session.get('user_name')

    return render_template('influencer_dashboard.html', campaigns=campaigns,user=user_name,ad_requests=ad_requests, public_campaigns=public_campaigns)




@app.route('/update_ad_request_status', methods=['POST'])
def update_ad_request_status():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not logged in

    ad_request_id = request.form.get('ad_request_id')
    new_status = request.form.get('new_status')

    # Fetch the ad request from the database
    ad_request = AdRequest.query.get(ad_request_id)

    if ad_request and ad_request.campaign.sponsor_id == session['user_id']:
        # Update the status of the ad request
        ad_request.status = new_status
        db.session.commit()

    return redirect(url_for('sponsor_dashboard'))

@app.route("/create_adreq", methods=["GET", "POST"])
def create_adreq():
    if request.method == "POST":
        # Get form data
        requirements = request.form['requirements']
        payment_amount = float(request.form['payment_amount'])
        # status = request.form['status']
        campaign_id = int(request.form['campaign_id'])
        influencer_id = int(request.form['influencer_id'])

        # Create a new AdRequest object
        new_ad_request = AdRequest(
            requirements=requirements,
            payment_amount=payment_amount,
            status="pending",
            campaign_id=campaign_id,
            influencer_id=influencer_id
        )

        # Add the ad request to the database
        db.session.add(new_ad_request)
        db.session.commit()

        # Redirect to a page showing all ad requests or a success page
        return redirect(url_for('sponsor_dashboard'))

    # Handle GET request: Fetch all campaigns and influencers
    campaigns = Campaign.query.all()
    influencers = User.query.filter_by(role='Influencer').all()

    # Render the form template
    return render_template('sponsor_dashboard.html', campaigns=campaigns, influencers=influencers)

@app.route("/negotiate",methods=["GET","POST"])
def negotiate():
    if request.method=="POST":
        req_amount=request.form["req_amount"]
        ad_req_id=int(request.form["ad_request_id"])
        print("id is",ad_req_id)

        req_inf=req_from_inf(
            req_amount=req_amount,
            ad_request_id=ad_req_id
            )
        
        db.session.add(req_inf)
        db.session.commit()
        
        flash(f'Request sent successfully!')
        return redirect("/influencer_dashboard")
    
@app.route("/accept", methods=["POST"])
def accept():
    if request.method == "POST":
        ad_req_id = int(request.form["ad_request_id"])
        status = request.form["status"]  # Get the status from the form submission

        # Query the ad_request by id
        ad_request = AdRequest.query.get(ad_req_id)

        if ad_request:
            # Update the status of the ad_request
            ad_request.status = status

            # Save the changes to the database
            db.session.commit()

            flash(f'Ad request {ad_req_id} status updated to {status}.')
        else:
            flash(f'Ad request with ID {ad_req_id} not found.')

        return redirect("/influencer_dashboard")
    
    
@app.route("/reject", methods=["POST"])
def reject():
    if request.method == "POST":
        ad_req_id = int(request.form["ad_request_id"])
        status = request.form["status"]  # Get the status from the form submission

        # Query the ad_request by id
        ad_request = AdRequest.query.get(ad_req_id)

        if ad_request:
            # Update the status of the ad_request
            ad_request.status = status

            # Save the changes to the database
            db.session.commit()

            flash(f'Ad request {ad_req_id} status updated to {status}.')
        else:
            flash(f'Ad request with ID {ad_req_id} not found.')

        return redirect("/influencer_dashboard")
    
@app.route("/accept_sp", methods=["POST"])
def accept_sp():
    if request.method == "POST":
        ad_req_id = int(request.form["ad_request_id"])
        status = request.form["status"]  # Get the status from the form submission
        amount=float(request.form["new_amount"])
        # Query the ad_request by id
        ad_request = AdRequest.query.get(ad_req_id)
        
        

        if ad_request:
            # Update the status of the ad_request
            ad_request.status = status
            ad_request.payment_amount=amount

            # Save the changes to the database
            db.session.commit()

            flash(f'Ad request {ad_req_id} status updated to {status}.')
        else:
            flash(f'Ad request with ID {ad_req_id} not found.')

        return redirect("/sponsor_dashboard")

    
@app.route("/reject_sp", methods=["POST"])
def reject_sp():
    if request.method == "POST":
        ad_req_id = int(request.form["ad_request_id"])
        status = request.form["status"]  # Get the status from the form submission

        # Query the ad_request by id
        ad_request = AdRequest.query.get(ad_req_id)

        if ad_request:
            # Update the status of the ad_request
            ad_request.status = status

            # Save the changes to the database
            db.session.commit()

            flash(f'Ad request {ad_req_id} status updated to {status}.')
        else:
            flash(f'Ad request with ID {ad_req_id} not found.')

        return redirect("/sponsor_dashboard")
    
@app.route('/flag_campaign/<int:campaign_id>', methods=['POST'])
def flag_campaign(campaign_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if user.role != 'Admin':
        return redirect(url_for('index'))

    campaign = Campaign.query.get(campaign_id)
    if campaign:
        campaign.flagged = True
        db.session.commit()
        flash(f'Campaign {campaign.name} has been flagged.')

    return redirect(url_for('admin_dashboard'))

@app.route('/flag_user/<int:user_id>', methods=['POST'])
def flag_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if user.role != 'Admin':
        return redirect(url_for('index'))

    user = User.query.get(user_id)
    if user:
        user.flagged = True
        db.session.commit()
        flash(f'User {user.name} has been flagged.')

    return redirect(url_for('admin_dashboard'))


# @app.route('/update_campaign/<int:id>', methods=["GET",'POST'])
# def update_campaign(id):
#     if request.method=="POST":
#         name=request.form["name"]
#         des=request.form["description"]
#         start_date=request.form["start_date"]
#         end_date=request.form["end_date"]
#         budget=request.form["budget"]
#         ind_pay=request.form["ind_pay"]
#         vis=request.form["visibility"]
#         goals=request.form["goals"]
#
#         campaign = Campaign.query.get(id)
#         campaign.name=name
#         campaign.description=des
#         campaign.start_date=start_date
#         campaign.end_date=end_date
#         campaign.budget=budget
#         campaign.ind_pay=ind_pay
#         campaign.visibility=vis
#         campaign.goals=goals
#
#         db.session.commit()
#         flash('Campaign updated successfully!', 'success')
#
#     campaign = Campaign.query.get(id)
#     print(campaign.id)
#     print(campaign.name)
#     print(campaign.description)
#     campaign_id = id
#     campaign = Campaign.query.get(campaign_id)
#
#     return render_template("cam_update.html",campaign=campaign)

@app.route('/update_campaign/<int:id>', methods=["GET", "POST"])
def update_campaign(id):
    campaign = Campaign.query.get(id)
    if request.method == "POST":
        # Extract form data
        name = request.form.get("name")
        description = request.form.get("description")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        budget = request.form.get("budget")
        ind_pay = request.form.get("ind_pay")
        visibility = request.form.get("visibility")
        goals = request.form.get("goals")
    
        # Update campaign with new data
        campaign.name = name
        campaign.description = description
        campaign.start_date = start_date
        campaign.end_date = end_date
        campaign.budget = budget
        campaign.ind_pay = ind_pay
        campaign.visibility = visibility
        campaign.goals = goals

        # Commit changes to the database
        db.session.commit()
        flash('Campaign updated successfully!', 'success')

    return render_template("cam_update.html", campaign=campaign)


# Route to delete a campaign
@app.route('/delete_campaign/<int:id>', methods=['POST'])
def delete_campaign(id):
    campaign_id = id
    campaign = Campaign.query.get(campaign_id)
    if campaign:
        ad_req=AdRequest.query.filter_by(campaign_id=id).all()
        if ad_req:
             for req in ad_req:
                 db.session.delete(req)
                 db.session.commit()

        db.session.delete(campaign)
        db.session.commit()
        flash('Campaign deleted successfully!', 'success')
    else:
        flash('Campaign not found.', 'error')
    
    return redirect(url_for('sponsor_dashboard'))



@app.route('/delete_campaignadmin/<int:id>', methods=['GET','POST'])
def delete_campaignadmin(id):
    campaign_id = id
    campaign = Campaign.query.get(campaign_id)
    if campaign:
        ad_req=AdRequest.query.filter_by(campaign_id=id).all()
        if ad_req:
             for req in ad_req:
                 db.session.delete(req)
                 db.session.commit()

        db.session.delete(campaign)
        db.session.commit()
        flash('Campaign deleted successfully!', 'success')
    else:
        flash('Campaign not found.', 'error')
    
    return redirect(url_for('admin-dashboard'))

@app.route('/delete/<int:ad_request_id>', methods=['GET',"POST"])
def delete(ad_request_id):
    if request.method=="POST":
       ad_request = AdRequest.query.get_or_404(ad_request_id)
       db.session.delete(ad_request)
       db.session.commit()
       return redirect(url_for('sponsor_dashboard'))


@app.route('/delete_user/<int:user_id>', methods=['GET'])
def delete_user(user_id):
    thisuser = User.query.get_or_404(user_id)
    camp_list = Campaign.query.all()
    ad_req_list = AdRequest.query.all()
    if thisuser.role == "Admin":
        return "Can not be deleted"
    for camp in camp_list:
        if camp.sponsor_id == thisuser.id:
            for ad_req in ad_req_list:
                if ad_req.campaign_id == camp.id:
                    db.session.delete(ad_req)
            db.session.delete(camp)
    for ad_req in ad_req_list:
        if ad_req.influencer_id == thisuser.id:
            db.session.delete(ad_req)
    db.session.delete(thisuser)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
